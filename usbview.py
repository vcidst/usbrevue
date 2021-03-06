#!/usr/bin/env python
#
# Copyright (C) 2011 Austin Leirvik <aua at pdx.edu>
# Copyright (C) 2011 Wil Cooley <wcooley at pdx.edu>
# Copyright (C) 2011 Joanne McBride <jirab21@yahoo.com>
# Copyright (C) 2011 Danny Aley <danny.aley@gmail.com>
# Copyright (C) 2011 Erich Ulmer <blurrymadness@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
from optparse import OptionParser
import pcapy
from usbrevue import Packet, USBMON_TRANSFER_TYPE, SETUP_REQUEST_TYPES
import codegen
from PyQt4.QtCore import Qt, QThread, QVariant, pyqtSignal, \
                         QAbstractTableModel, QModelIndex, \
                         QPersistentModelIndex, QTimer, QString
from PyQt4.QtGui import *


class PcapThread(QThread):
    """ Thread responsible for reading pcap data from input and signalling
 arriving packets. """
    new_packet = pyqtSignal(object)
    eof = pyqtSignal()
    dump_opened = pyqtSignal(object)

    def __init__(self, source='-', dest='-'):
        QThread.__init__(self)
        self.source = source
        self.dest = dest

    def run(self):
        if self.source == '-' and sys.stdin.isatty():
            return
        pcap = pcapy.open_offline(self.source)
        # don't output anything unless we're being piped/redirected
        if not (self.dest == '-' and sys.stdout.isatty()):
            out = pcap.dump_open(self.dest)
            sys.stdout.flush()
            self.dump_opened.emit(out)

        while 1:
            (hdr, pack) = pcap.next()
            if hdr is None:
                self.eof.emit()
                break
            self.new_packet.emit(Packet(hdr, pack))




# column indexes for packet model data
TIMESTAMP_COL = 0
ADDRESS_COL = 1
SETUP_COL = 2
DATA_COL = 3


class PacketModel(QAbstractTableModel):
    """ Qt model for packet data. """
    def __init__(self, parent = None):
        QAbstractTableModel.__init__(self, parent)
        self.packets = []
        self.headers = {TIMESTAMP_COL: "Timestamp",
                        ADDRESS_COL: "Address",
                        SETUP_COL: "Setup",
                        DATA_COL: "Data"}
        # timestamp of the first received packet
        self.first_ts = 0.0

    def rowCount(self, parent = QModelIndex()):
        return 0 if parent.isValid() else len(self.packets)

    def columnCount(self, parent = QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role = Qt.DisplayRole):
        row = index.row()
        col = index.column()
        pack = self.packets[row]

        if role == Qt.DisplayRole:
            if isinstance(pack, str):
                return pack
            elif col == TIMESTAMP_COL:
                return "%f" % (pack.ts_sec + pack.ts_usec/1e6 - self.first_ts)
            elif col == ADDRESS_COL:
                return pack.packet_summ
            elif col == DATA_COL:
                return pack.data_hexdump(64)
            elif col == SETUP_COL and pack.is_setup_packet:
                if pack.setup.bmRequestTypeType == 'standard':
                    return SETUP_REQUEST_TYPES[pack.setup.bRequest]
                return pack.setup.data_to_str()
        elif role == Qt.FontRole:
            if col in [SETUP_COL, ADDRESS_COL, DATA_COL]:
                return QFont("monospace")
            if isinstance(pack, str):
                font = QFont()
                font.setBold(True)
                return font
        elif role == Qt.ToolTipRole:
            if col == ADDRESS_COL:
                return '%s %s (%s, %s) ' % (pack.event_type_preposition,
                                            pack.address_verbose,
                                            pack.transfer_type,
                                            pack.endpoint_dir)
            if col == SETUP_COL and pack.is_setup_packet:
                return pack.setup.fields_to_str()
        elif role == Qt.BackgroundColorRole:
            if isinstance(pack, Packet):
                if pack.is_setup_packet:
                    return self.packet_color(pack)
                elif pack.is_event_type_callback and pack.is_control_xfer:
                    # find the corresponding submission, color accordingly
                    for i in xrange(row, -1, -1):
                        if isinstance(self.packets[i], Packet) and \
                                self.packets[i].event_type == 'S' and \
                                self.packets[i].busnum == pack.busnum and \
                                self.packets[i].devnum == pack.devnum and \
                                self.packets[i].epnum == pack.epnum:
                            return self.packet_color(self.packets[i])
        elif role == Qt.UserRole: # packet object
            return QVariant(pack)
 
        return QVariant()

    def packet_color(self, pack):
        if not pack.is_setup_packet:
            return QVariant()
        if pack.setup.bmRequestTypeType == 'standard':
            return QColor('lightgray')
        elif pack.setup.bmRequestTypeType == 'class_':
            return QColor(250, 230, 190)
        elif pack.setup.bmRequestTypeType == 'vendor':
            return QColor(190, 250, 190)

    def setData(self, index, value, role = Qt.EditRole):
        if role != Qt.EditRole or index.column() != DATA_COL:
            return False
        datastr = str(value.toString())
        try:
            data = map(lambda b: int(b, 16), datastr.split())
        except Exception:
            return False
        for i in xrange(len(data)):
            self.packets[index.row()].data[i] = data[i]
        self.dataChanged.emit(index, index)
        return True
        
    def headerData(self, section, orientation, role = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return QVariant()

    def flags(self, index):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == DATA_COL:
            flags = flags | Qt.ItemIsEditable
        return flags

    def removeRows(self, first, count, parent = None):
        last = first + count - 1
        self.beginRemoveRows(QModelIndex(), first, last)
        self.packets = self.packets[:first] + self.packets[last+1:]
        self.endRemoveRows()
        return True

    def clear(self):
        self.beginResetModel()
        self.packets = []
        self.first_ts = 0.0
        self.endResetModel()

    def new_packet(self, pack):
        l = len(self.packets)
        self.first_ts = self.first_ts or pack.ts_sec + pack.ts_usec/1e6
        self.beginInsertRows(QModelIndex(), l, l)
        self.packets.append(pack)
        self.endInsertRows()

    def new_annotation(self, note):
        l = len(self.packets)
        self.beginInsertRows(QModelIndex(), l, l)
        self.packets.append("*** " + str(note))
        self.endInsertRows()




class PacketFilterProxyModel(QSortFilterProxyModel):
    """ Proxy model for filtering displayed packets. """
    def __init__(self, parent = None):
        QSortFilterProxyModel.__init__(self, parent)
        self.expr = 'True'

    def set_filter(self, e):
        self.expr = str(e) or 'True'
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        packet = self.sourceModel().data(index, Qt.UserRole).toPyObject()
        if isinstance(packet, QString):
            return True
        try:
            return bool(eval(self.expr, USBMON_TRANSFER_TYPE, packet))
        except Exception:
            return False

    def clear(self):
        self.sourceModel().clear()




class HexEditDelegate(QItemDelegate):
    """ Delegate enabling editing of packet payload """
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        pack = index.model().data(index, Qt.UserRole).toPyObject()
        # refuse editing if there's no existing data
        if not pack.data:
            return
        # only accept a series of hex character pairs of the same length
        # as the existing data. '>' forces uppercase.
        editor.setInputMask('>' + ' '.join(["HH"] * len(pack.data)))
        editor.installEventFilter(self)
        editor.setFont(QFont("monospace"))
        return editor

    def setEditorData(self, editor, index):
        pack = index.model().data(index, Qt.UserRole).toPyObject()
        text = ' '.join(map(lambda x: "%02X" % x, pack.data))
        editor.setText(text)

    def setModelData(self, editor, model, index):
        if editor.hasAcceptableInput():
            model.setData(index, QVariant(editor.text()))

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        # ensure that the frame doesn't conceal any of the text
        rect.setTop(rect.top()-2)
        rect.setBottom(rect.bottom()+2)
        rect.setLeft(rect.left()-1)
        editor.setGeometry(rect)




class PacketView(QTreeView):
    dump_packet = pyqtSignal(object)

    def __init__(self, parent = None):
        QTreeView.__init__(self, parent)
        self.dump_selected_act = QAction("Dump selected", self)
        self.dump_selected_act.triggered.connect(self.dump_selected)
        self.remove_selected_act = QAction("Remove selected", self)
        self.remove_selected_act.triggered.connect(self.remove_selected)
        self.remove_selected_act.setShortcut(QKeySequence.Delete)
        self.addAction(self.remove_selected_act)
        self.remove_all_act = QAction("Remove all", self)
        self.remove_all_act.triggered.connect(self.remove_all)
        self.passthru_toggle = QAction("Passthrough", self)
        self.passthru_toggle.setCheckable(True)
        self.passthru_toggle.setChecked(True)
        self.autoscroll_toggle = QAction("Autoscroll", self)
        self.autoscroll_toggle.setCheckable(True)
        self.autoscroll_toggle.setChecked(False)
        self.pause_toggle = QAction("Pause capture", self)
        self.pause_toggle.setCheckable(True)
        self.pause_toggle.setChecked(False)
        self.copy_as_code_act = QAction("Copy as libusb code", self)
        self.copy_as_code_act.triggered.connect(self.copy_as_code)
        self.delegate = HexEditDelegate()
        self.setItemDelegateForColumn(DATA_COL, self.delegate)
        self.autoscroll_timer = QTimer(self)
        self.autoscroll_timer.setSingleShot(True)
        self.autoscroll_timer.timeout.connect(self.scrollToBottom)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction(self.dump_selected_act)
        menu.addAction(self.copy_as_code_act)
        menu.addSeparator()
        menu.addAction(self.remove_selected_act)
        menu.addAction(self.remove_all_act)
        menu.addSeparator()
        menu.addAction(self.autoscroll_toggle)
        menu.addAction(self.passthru_toggle)
        menu.addSeparator()
        menu.addAction(self.pause_toggle)
        menu.exec_(event.globalPos())

    def copy_as_code(self):
        selected = self.selectionModel().selectedRows()
        selected.sort(cmp=lambda x,y: cmp(x.row(), y.row()))
        s = ''
        deviceset = set()
        for idx in selected:
            pack = self.model().data(idx, Qt.UserRole).toPyObject()
            s += codegen.packet_to_libusb_code(pack)
            deviceset.add((pack.busnum, pack.devnum))
        QApplication.clipboard().setText(s)
        if len(deviceset) > 1:
            msgbox = QMessageBox()
            msgbox.setText("Warning: code generated for multiple devices")
            msgbox.setInformativeText("This is probably not what you want. Try filtering by device and/or bus number.")
            detailtext = 'Devices in selection:\n'
            for devtuple in deviceset:
                detailtext += 'Bus %d, device %d\n' % devtuple
            msgbox.setDetailedText(detailtext)
            msgbox.setIcon(QMessageBox.Warning)
            msgbox.exec_()

    def remove_selected(self):
        rows = self.selectionModel().selectedRows()
        rows = map(lambda x: QPersistentModelIndex(x), rows)
        for idx in rows:
            self.model().removeRow(idx.row())

    def remove_all(self):
        self.model().clear()

    def rowsInserted(self, parent, start, end):
        QTreeView.rowsInserted(self, parent, start, end)
        if self.autoscroll_toggle.isChecked() and not self.autoscroll_timer.isActive():
            self.autoscroll_timer.start(50)

        for row in xrange(start, end+1):
            idx = self.model().index(row, 0, parent)
            pack = self.model().data(idx, Qt.UserRole).toPyObject()
            if isinstance(pack, QString):
                self.setFirstColumnSpanned(row, parent, True)

    def dump_selected(self):
        selected = self.selectionModel().selectedRows()
        self.passthru_toggle.setChecked(False)
        # sort by row - dump packets in the order they appear
        selected.sort(cmp=lambda x,y: cmp(x.row(), y.row()))
        for idx in selected:
            packet = self.model().data(idx, 32).toPyObject()
            self.dump_packet.emit(packet)
        
        



class FilterWidget(QWidget):
    new_view_filter = pyqtSignal(str)
    new_cap_filter = pyqtSignal(str)

    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        self.view_filter_edit = QLineEdit()
        self.view_filter_clear = QPushButton("Clear")
        self.cap_filter_edit = QLineEdit()
        self.cap_filter_clear = QPushButton("Clear")

        filter_tip = """Available fields include:
event_type:\t'C', 'S', or 'E' for Callback, Submission, or Error
xfer_type:\tThe transfer type - control, isochronous, bulk, or interrupt
epnum:\tThe endpoint number
devnum:\tThe device number
busnum:\tThe bus number
data:\tA list of transmitted bytes of data"""

        self.cap_filter_edit.setToolTip(
                "Filter captured packets with a python expression\n\n" +
                filter_tip)
        self.view_filter_edit.setToolTip(
                "Filter visible packets with a python expression\n\n" +
                filter_tip)
        self.cap_filter_clear.setToolTip("Clear capture filter")
        self.view_filter_clear.setToolTip("Clear display filter")

        # Temporary workaround for Ubuntu 10.10 -- placeholderText was
        # introduced in Qt 4.7, but PyQt4 4.7.4 has no bindings for it.
        if hasattr(self.view_filter_edit, "setPlaceholderText"):
            self.view_filter_edit.setPlaceholderText("Display filter")
            self.cap_filter_edit.setPlaceholderText("Capture filter")

        self.hb = QHBoxLayout()
        self.hb.addWidget(self.view_filter_edit)
        self.hb.addWidget(self.view_filter_clear)
        self.hb.addWidget(self.cap_filter_edit)
        self.hb.addWidget(self.cap_filter_clear)
        self.setLayout(self.hb)

        self.view_filter_clear.clicked.connect(self.clear_view_filter)
        self.cap_filter_clear.clicked.connect(self.clear_cap_filter)
        self.view_filter_edit.returnPressed.connect(self.update_view_filter)
        self.cap_filter_edit.returnPressed.connect(self.update_cap_filter)
        
    def update_view_filter(self):
        #TODO validation
        self.new_view_filter.emit(str(self.view_filter_edit.text()))

    def clear_view_filter(self):
        self.view_filter_edit.setText("")
        self.update_view_filter()

    def update_cap_filter(self):
        #TODO validation
        self.new_cap_filter.emit(str(self.cap_filter_edit.text()))

    def clear_cap_filter(self):
        self.cap_filter_edit.setText("")
        self.update_cap_filter()



class USBView(QApplication):
    def __init__(self, argv, options, args):
        QApplication.__init__(self, argv)
        self.w = QWidget()
        self.w.resize(1000, 800)

        self.packetmodel = PacketModel()
        self.proxy = PacketFilterProxyModel()
        self.proxy.setSourceModel(self.packetmodel)
        self.packetview = PacketView()
        self.packetview.setRootIsDecorated(False)
        self.packetview.setModel(self.proxy)
        self.packetview.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.packetview.setUniformRowHeights(True)
        self.packetview.setAllColumnsShowFocus(True)
        qfm = QFontMetrics(QFont('monospace'))
        self.packetview.setColumnWidth(ADDRESS_COL, qfm.width('X X:XX:XX (XX)'))
        self.packetview.setColumnWidth(SETUP_COL, qfm.width('XX XX XXXX XXXX XXXX'))
        self.packetview.dump_packet.connect(self.dump_packet)
        self.packetview.passthru_toggle.toggled.connect(self.passthru_toggled)
        self.packetview.pause_toggle.toggled.connect(self.pause_toggled)

        self.filterpane = FilterWidget()
        self.filterpane.new_view_filter.connect(self.proxy.set_filter)
        self.filterpane.new_cap_filter.connect(self.new_cap_filter)

        self.annotator = QLineEdit()
        self.annotator.returnPressed.connect(self.new_annotation)
        if hasattr(self.annotator, "setPlaceholderText"):
            self.annotator.setPlaceholderText("Annotation")

        self.vb = QVBoxLayout()
        self.vb.addWidget(self.filterpane)
        self.vb.addWidget(self.packetview)
        self.vb.addWidget(self.annotator)
        self.w.setLayout(self.vb)
        self.w.show()

        if sys.stdin.isatty() and len(args) > 0:
            self.pcapthread = PcapThread(source=args[0])
        else:
            self.pcapthread = PcapThread()
        self.pause_toggled(False)
        self.pcapthread.dump_opened.connect(self.dump_opened)
        self.pcapthread.start()

        self.dumper = None
        self.passthru_toggled(options.passthru)
        self.filterexpr = None

    def new_annotation(self):
        note = self.annotator.text()
        self.annotator.clear()
        self.packetmodel.new_annotation(note)
	
    def dump_opened(self, dumper):
        self.dumper = dumper

    def passthru_toggled(self, state):
        self.passthru = state
        if self.packetview.passthru_toggle.isChecked() != state:
            self.packetview.passthru_toggle.setChecked(state)

    def pause_toggled(self, state):
        if state:
            self.pcapthread.new_packet.disconnect(self.new_packet)
        else:
            self.pcapthread.new_packet.connect(self.new_packet)
    
    def new_packet(self, packet):
        if self.filterexpr:
            try:
                if not eval(self.filterexpr, USBMON_TRANSFER_TYPE, packet):
                    return
            except Exception:
                return

        if self.passthru:
            self.dump_packet(packet)
        self.packetmodel.new_packet(packet)

    def new_cap_filter(self, e):
        self.filterexpr = str(e)

    def dump_packet(self, pack):
        if self.dumper is not None:
            try:
                #TODO dump annotations?
                self.dumper.dump(pack.hdr, pack.repack())
                sys.stdout.flush()
            except Exception:
                self.dumper = None


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-p", "--passthru", default=False, action="store_true",
            help="Start with passthru enabled.")
    (options, args) = parser.parse_args()
    app = USBView(sys.argv, options, args)
    sys.exit(app.exec_())


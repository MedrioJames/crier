"""Ensure only one Crier runs. A second launch pings the first to show its controls."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtCore import QSharedMemory

_KEY = "crier-single-instance"
_PIPE = "crier-ipc"


class SingleInstance(QObject):
    """Usage:
        si = SingleInstance()
        if si.already_running():
            si.signal_existing(); sys.exit(0)
        si.start_server()
        si.activate.connect(...)   # fired when another launch pings us
    """

    activate = Signal()

    def __init__(self):
        super().__init__()
        self._shared = QSharedMemory(_KEY)
        self._server = None

    def already_running(self) -> bool:
        # If we can attach, someone else created it first.
        if self._shared.attach():
            return True
        # Otherwise claim it (1 byte is enough as a flag).
        return not self._shared.create(1)

    def signal_existing(self):
        sock = QLocalSocket()
        sock.connectToServer(_PIPE)
        if sock.waitForConnected(500):
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(500)
            sock.disconnectFromServer()

    def start_server(self):
        QLocalServer.removeServer(_PIPE)  # clear any stale socket
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_conn)
        self._server.listen(_PIPE)

    def _on_conn(self):
        conn = self._server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: (conn.readAll(), self.activate.emit()))

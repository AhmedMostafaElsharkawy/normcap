"""Find new version on github or pypi."""
import json
import logging
import re

from packaging import version
from PySide6 import QtCore, QtWidgets

from normcap import __version__
from normcap.gui.constants import URLS
from normcap.gui.downloader_urllib import Downloader
from normcap.gui.utils import get_icon, set_cursor

logger = logging.getLogger(__name__)


class Communicate(QtCore.QObject):
    """TrayMenus' communication bus."""

    on_version_parsed = QtCore.Signal(str)
    on_new_version_found = QtCore.Signal(str)
    on_click_get_new_version = QtCore.Signal(str)


class UpdateChecker(QtCore.QObject):
    """Helper to check for a new version."""

    def __init__(self, parent, packaged: bool = False):
        super().__init__(parent)
        self.packaged = packaged
        self.com = Communicate()
        self.downloader = Downloader()
        self.downloader.com.on_download_finished.connect(self.parse_response_to_version)
        self.com.on_version_parsed.connect(self.check_if_version_is_new)
        self.com.on_new_version_found.connect(self.show_update_message)
        self.message_box = self._create_message_box()

    def parse_response_to_version(self, text: str):
        """Parse the tag version from the response and emit version retrieved signal."""
        newest_version = None

        try:
            if self.packaged:
                match = re.search(r"/releases/tag/v(\d+\.\d+\.\d+)\"", text)
                if match and match[1]:
                    newest_version = match[1]
            else:
                data = json.loads(text)
                newest_version = data["info"]["version"].strip()
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Parsing response of update check failed: %s", e)

        if newest_version:
            self.com.on_version_parsed.emit(newest_version)
        else:
            logger.error("Couldn't detect remote version. Update check won't work!")

    def check(self):
        """Start the update check."""
        url = URLS.releases_atom if self.packaged else f"{URLS.pypi}/json"
        logger.debug("Search for new version on %s", url)
        self.downloader.get(url)

    @staticmethod
    def _create_message_box():
        message_box = QtWidgets.QMessageBox()

        # Necessary on wayland for main window to regain focus:
        message_box.setWindowFlags(QtCore.Qt.Popup)

        message_box.setIconPixmap(get_icon("normcap.png").pixmap(48, 48))
        message_box.setStandardButtons(
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel
        )
        message_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
        return message_box

    def check_if_version_is_new(self, newest_version):
        """Show dialog informing about available update."""
        if newest_version:
            logger.debug(
                "Newest version: %s (installed: %s)", newest_version, __version__
            )
            if version.parse(newest_version) > version.parse(__version__):
                self.com.on_new_version_found.emit(newest_version)

    def show_update_message(self, new_version):
        """Show dialog informing about available update."""
        text = f"<b>NormCap v{new_version} is available.</b> (You have v{__version__})"
        if self.packaged:
            info_text = (
                "You can download the new version for your operating system from "
                "GitHub.\n\n"
                "Do you want to visit the release website now?"
            )
            update_url = URLS.releases
        else:
            info_text = (
                "You should be able to upgrade from command line with "
                "'pip install normcap --upgrade'.\n\n"
                "Do you want to view the changelog on github?"
            )
            update_url = URLS.changelog

        self.message_box.setText(text)
        self.message_box.setInformativeText(info_text)

        set_cursor(QtCore.Qt.ArrowCursor)
        choice = self.message_box.exec_()
        set_cursor(QtCore.Qt.CrossCursor)

        if choice == 1024:
            self.com.on_click_get_new_version.emit(update_url)

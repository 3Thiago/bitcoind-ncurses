#!/usr/bin/env python
import curses
import calendar
import gevent
import time

import global_mod as g
import getstr

class BlockViewer(object):
    def __init__(self, block_store, window):
        self._block_store = block_store
        self._window = window

        self._mode = None # TODO debug

        self._browse_height = None

        self._keymap = {
            curses.KEY_DOWN: (self._scroll_down, ),
            curses.KEY_UP: (self._scroll_up, ),

            curses.KEY_HOME: (self._seek, -1000),
            curses.KEY_END: (self._seek, 1000),

            # ord('l'): go_to_latest_block,
            # ord('L'): go_to_latest_block,

            ord('j'): (self._seek, -1),
            ord('J'): (self._seek, -1),

            ord('k'): (self._seek, 1),
            ord('K'): (self._seek, 1),
        }

        self._reset_cursors()

    def _reset_cursors(self):
        self._cursor = 0
        self._offset = 0

    def on_block(self, block):
        if not self._browse_height:
            self._browse_height = block.blockheight

        if self._mode and self._mode == "block":
            self.draw()

    def draw(self):
        def draw_transactions(block):
            # TODO: fix this
            # window_height = state['y'] - 6
            window_height = 10
            win_transactions = curses.newwin(window_height, 75, 5, 0)

            tx_count = len(block.tx)
            bytes_per_tx = block.size // tx_count

            win_transactions.addstr(0, 1, "Transactions: " + ("% 4d" % tx_count + " (" + str(bytes_per_tx) + " bytes/tx)").ljust(26) + "(UP/DOWN: scroll, ENTER: view)", curses.A_BOLD + curses.color_pair(5))

            # reset cursor if it's been resized off the bottom
            if self._cursor > self._offset + (window_height-2):
                self._offset = self._cursor - (window_height-2)

            # reset cursor if the block changed and it's nonsense now
            if self._cursor >= tx_count or self._offset >= tx_count:
                self._reset_cursors()

            offset = self._offset

            for index in range(offset, offset+window_height-1):
                if index < tx_count:
                    if index == self._cursor:
                        win_transactions.addstr(index+1-offset, 1, ">", curses.A_REVERSE + curses.A_BOLD)

                    condition = (index == offset+window_height-2) and (index+1 < tx_count)
                    condition = condition or ( (index == offset) and (index > 0) )

                    if condition:
                        win_transactions.addstr(index+1-offset, 3, "...")
                    else:
                        win_transactions.addstr(index+1-offset, 3, block.tx[index])

            win_transactions.refresh()

        def draw_block(block):
            win_header = curses.newwin(5, 75, 0, 0)
            win_header.addstr(0, 1, "height: " + str(block.blockheight).zfill(6) + "    (J/K: browse, HOME/END: quicker, L: latest, G: seek)", curses.A_BOLD)
            win_header.addstr(1, 1, "hash: " + block.blockhash, curses.A_BOLD)
            win_header.addstr(2, 1, "root: " + block.merkleroot, curses.A_BOLD)
            win_header.addstr(3, 1, "{} bytes ({} KB)".format(block.size, block.size//1024), curses.A_BOLD)
            win_header.addstr(3, 26, "diff: {:,d}".format(int(block.difficulty)), curses.A_BOLD)
            win_header.addstr(3, 52, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(block.time)), curses.A_BOLD)
            win_header.addstr(4, 51, ("v" + str(block.version)).rjust(20), curses.A_BOLD)
            win_header.refresh()

        def draw_no_block():
            win_header = curses.newwin(5, 75, 0, 0)
            win_header.addstr(0, 1, "height: " + str(self._browse_height).zfill(6) + " (no block information loaded)", curses.A_BOLD + curses.color_pair(3))
            win_header.addstr(1, 1, "press 'G' to enter a block hash, height, or timestamp", curses.A_BOLD)
            win_header.refresh()

        self._window.clear()
        self._window.refresh()

        if self._browse_height is not None:
            # TODO: try/except on KeyError here?
            try:
                blockhash = self._block_store.get_hash(self._browse_height)
                block = self._block_store.get_block(blockhash)
            except KeyError:
                draw_no_block()
                return

            draw_block(block)
            draw_transactions(block)

        else:
            draw_no_block()

    def get_selected_txid(self):
        if self._browse_height is None:
            return None

        try:
            blockhash = self._block_store.get_hash(self._browse_height)
            block = self._block_store.get_block(blockhash)
        except KeyError:
            return None

        if len(block.tx) <= self._cursor:
            return None

        return block.tx[self._cursor]

    def _seek(self, delta):
        if self._browse_height is None:
            return

        new_browse_height = self._browse_height + delta
        if new_browse_height < 0:
            return

        self._reset_cursors()
        self._browse_height = new_browse_height
        try:
            blockhash = self._block_store.get_hash(self._browse_height)
            self.draw()
        except KeyError:
            self._block_store.request_blockheight(self._browse_height)

    def _seek_back_one(self):
        self._seek(-1)

    def _seek_forward_one(self):
        self._seek(1)

    def _seek_back_thousand(self):
        self._seek(-1000)

    def _seek_forward_thousand(self):
        self._seek(1000)

    def _scroll_down(self):
        if self._browse_height is None:
            return

        try:
            blockhash = self._block_store.get_hash(self._browse_height)
            block = self._block_store.get_block(blockhash)
        except KeyError:
            return

        if self._cursor < (len(block.tx) - 1):
            self._cursor += 1
            window_height = 10
            if (self._cursor - self._offset) > window_height-2:
                self._offset += 1
            self.draw()

    def _scroll_up(self):
        if self._browse_height is None:
            return

        if self._cursor > 0:
            if (self._cursor - self._offset) == 0:
                self._offset -= 1
            self._cursor -= 1
            self.draw()

    def handle_hotkey(self, key):
        if not self._mode or self._mode != "block":
            return

        if key in self._keymap:
            fn, *args = self._keymap[key]
            fn(*args)
            return True

        return False

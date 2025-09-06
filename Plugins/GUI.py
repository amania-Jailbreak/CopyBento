NAME = "GUI"
from Cocoa import (
    NSApplication,
    NSApp,
    NSRunningApplication,
    NSApplicationActivationPolicyRegular,
)
from Cocoa import (
    NSWindow,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskFullSizeContentView,
)
from Cocoa import NSScrollView, NSTableView, NSTableColumn, NSObject
from Cocoa import NSMakeRect, NSRect, NSPoint, NSSize
from Cocoa import NSButton, NSBezelStyleRounded, NSSearchField
from Cocoa import NSTextField, NSTextView
from Cocoa import NSView, NSImageView, NSImageScaleProportionallyUpOrDown
from Cocoa import NSFont
from Cocoa import NSColor
from Cocoa import NSVisualEffectView
from Cocoa import NSVisualEffectBlendingModeBehindWindow, NSVisualEffectStateActive
from Cocoa import NSViewWidthSizable, NSViewHeightSizable
from Cocoa import (
    NSWindowTitleHidden,
    NSWindowCloseButton,
    NSWindowMiniaturizeButton,
    NSWindowZoomButton,
)
from Cocoa import NSAlert, NSAlertStyleInformational
from Cocoa import NSImage
from Cocoa import NSEvent
from Cocoa import NSWorkspace
from Foundation import NSURL
from Foundation import NSDistributedNotificationCenter
import time
import objc
import json, os, sys, subprocess

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

sys.path.append(BASE_DIR)
from Library import mcb
from Library import settings as app_settings
from Plugins import history_provider


# --- Plugin hooks ---
def on_clipboard(data_type, value):
    # GUI plugin does not transform clipboard
    return None


def on_startup(event_manager):
    # Register hotkey and event to open the GUI
    try:
        event_manager.register_hotkey("shift+cmd+v", "open_history_gui")

        @event_manager.event("open_history_gui")
        def _open_gui():
            try:
                print("Opening GUI...")
                # Ask any existing GUI process to close itself first
                try:
                    NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_(
                        "CopyBento.GUI.Close", None
                    )
                    # Small delay to give time to terminate
                    time.sleep(0.05)
                except Exception:
                    pass
                py = sys.executable or "python3"
                subprocess.Popen([py, os.path.abspath(__file__)])
            except Exception:
                pass

    except Exception:
        pass


class HistoryDataSource(NSObject):
    def init(self):
        self = objc.super(HistoryDataSource, self).init()
        if self is None:
            return None
        self.items = []
        self.filtered = []
        self.query = ""
        return self

    def loadData(self):
        try:
            self.items = history_provider.get_history() or []
        except Exception:
            self.items = []
        self.filtered = list(self.items)

    def numberOfRowsInTableView_(self, table):
        return len(self.filtered)

    def tableView_objectValueForTableColumn_row_(self, table, column, row):
        if row < 0 or row >= len(self.filtered):
            return ""
        item = self.filtered[row]
        ts = item.get("ts")
        preview = item.get("preview", "")
        return f"{preview}"

    # Always allow selection of rows
    def tableView_shouldSelectRow_(self, table, row):
        try:
            return True
        except Exception:
            return True

    # Provide view-based cells with an optional thumbnail image + text
    def tableView_viewForTableColumn_row_(self, table, column, row):
        try:
            if row < 0 or row >= len(self.filtered):
                return None
            item = self.filtered[row]
            text = item.get("preview", "")
            identifier = "CellView"
            view = table.makeViewWithIdentifier_owner_(identifier, self)
            img_size = (
                int(max(24, min(48, int(getattr(table, "rowHeight", lambda: 36)()))))
                if hasattr(table, "rowHeight")
                else 36
            )
            padding = 6
            if view is None:
                # Container view
                view = NSView.alloc().initWithFrame_(
                    NSMakeRect(0, 0, column.width(), max(24, img_size + padding * 2))
                )
                try:
                    view.setIdentifier_(identifier)
                except Exception:
                    pass
                # Image view (tag 1)
                iv = NSImageView.alloc().initWithFrame_(
                    NSMakeRect(padding, padding, img_size, img_size)
                )
                try:
                    iv.setImageScaling_(NSImageScaleProportionallyUpOrDown)
                except Exception:
                    pass
                iv.setEditable_(False)
                iv.setAnimates_(False)
                iv.setAllowsCutCopyPaste_(False)
                iv.setTag_(1)
                view.addSubview_(iv)
                # Text field (tag 2)
                tf = NSTextField.alloc().initWithFrame_(
                    NSMakeRect(
                        padding * 2 + img_size,
                        padding,
                        max(0, column.width() - (img_size + padding * 3)),
                        max(20, img_size),
                    )
                )
                tf.setBezeled_(False)
                tf.setBordered_(False)
                tf.setEditable_(False)
                tf.setSelectable_(False)
                try:
                    tf.setFont_(NSFont.systemFontOfSize_(16))
                except Exception:
                    pass
                try:
                    tf.setDrawsBackground_(False)
                except Exception:
                    pass
                tf.setTag_(2)
                view.addSubview_(tf)
            # Update content
            # Find subviews by tag
            iv = None
            tf = None
            try:
                for sv in list(view.subviews() or []):
                    try:
                        tag = int(sv.tag())
                        if tag == 1:
                            iv = sv
                        elif tag == 2:
                            tf = sv
                    except Exception:
                        pass
            except Exception:
                pass
            if tf is not None:
                tf.setStringValue_(text)
                try:
                    tf.setFont_(NSFont.systemFontOfSize_(16))
                except Exception:
                    pass
            # Handle image preview
            if item.get("type") == "image" and iv is not None:
                try:
                    path = item.get("image_path")
                    if path and os.path.exists(path):
                        nsimg = NSImage.alloc().initWithContentsOfFile_(path)
                        iv.setImage_(nsimg)
                    else:
                        iv.setImage_(None)
                except Exception:
                    try:
                        iv.setImage_(None)
                    except Exception:
                        pass
            elif iv is not None:
                try:
                    iv.setImage_(None)
                except Exception:
                    pass
            return view
        except Exception:
            return None

    def filter_(self, query: str):
        q = (query or "").lower()
        self.query = q
        if not q:
            self.filtered = list(self.items)
        else:
            out = []
            for it in self.items:
                if it.get("type") == "text":
                    src = (it.get("text") or "").lower()
                else:
                    src = "[image]"
                if q in src:
                    out.append(it)
            self.filtered = out


class KeyboardTableView(NSTableView):
    def acceptsFirstResponder(self):
        try:
            return True
        except Exception:
            return True

    def keyDown_(self, event):
        try:
            kc = int(event.keyCode())
            # Return / Keypad Enter
            if kc in (36, 76):
                owner = getattr(self, "owner", None)
                if owner is not None:
                    owner.onCopy_(self)
                    return
            # Escape
            if kc == 53:
                owner = getattr(self, "owner", None)
                if owner is not None:
                    owner.onClose_(self)
                    return
        except Exception:
            pass
        # Let NSTableView handle arrows and other keys (selection movement, type select)
        objc.super(KeyboardTableView, self).keyDown_(event)


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.ds = HistoryDataSource.alloc().init()
        self.ds.loadData()
        self._keyMonitor = None
        self.autoPaste = True
        try:
            self.prevApp = NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            self.prevApp = None
        # Listen for external close requests (single-window behavior)
        try:
            self._distCenter = NSDistributedNotificationCenter.defaultCenter()
            self._distCenter.addObserver_selector_name_object_(
                self, "onExternalClose:", "CopyBento.GUI.Close", None
            )
        except Exception:
            self._distCenter = None

        w, h = 720, 480
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, w, h),
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable,
            2,
            False,
        )
        self.window.setTitle_("CopyBento History")
        self.window.center()
        # Fill content under titlebar and hide titlebar UI
        try:
            self.window.setStyleMask_(
                int(self.window.styleMask()) | int(NSWindowStyleMaskFullSizeContentView)
            )
        except Exception:
            pass
        # Make background semi-transparent
        try:
            self.window.setOpaque_(False)
        except Exception:
            pass
        try:
            # Slightly transparent whole window (affects titlebar too)
            self.window.setAlphaValue_(0.94)
        except Exception:
            pass
        try:
            # Set a translucent background color for the content area
            self.window.setBackgroundColor_(
                NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.85)
            )
        except Exception:
            pass
        try:
            # Blend the titlebar with content for a cleaner translucent look
            self.window.setTitlebarAppearsTransparent_(True)
        except Exception:
            pass
        try:
            # Hide the window title text
            self.window.setTitleVisibility_(NSWindowTitleHidden)
        except Exception:
            pass
        # Hide standard window buttons (traffic lights)
        try:
            btn = self.window.standardWindowButton_(NSWindowCloseButton)
            if btn:
                btn.setHidden_(True)
        except Exception:
            pass
        try:
            btn = self.window.standardWindowButton_(NSWindowMiniaturizeButton)
            if btn:
                btn.setHidden_(True)
        except Exception:
            pass
        try:
            btn = self.window.standardWindowButton_(NSWindowZoomButton)
            if btn:
                btn.setHidden_(True)
        except Exception:
            pass
        # Allow dragging the window by clicking and dragging on background areas
        try:
            self.window.setMovableByWindowBackground_(True)
        except Exception:
            pass
        try:
            self.window.makeKeyAndOrderFront_(None)
            self.window.makeFirstResponder_(self)
        except Exception:
            pass

        # Add a background visual effect view (blur) that fills the content
        try:
            content = self.window.contentView()
            effect = NSVisualEffectView.alloc().initWithFrame_(content.bounds())
            try:
                effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
            except Exception:
                pass
            try:
                effect.setState_(NSVisualEffectStateActive)
            except Exception:
                pass
            # Choose a stronger-looking material first, then fall back
            set_material_done = False
            try:
                from Cocoa import NSVisualEffectMaterialHUDWindow

                effect.setMaterial_(NSVisualEffectMaterialHUDWindow)
                set_material_done = True
            except Exception:
                pass
            if not set_material_done:
                try:
                    from Cocoa import NSVisualEffectMaterialPopover

                    effect.setMaterial_(NSVisualEffectMaterialPopover)
                    set_material_done = True
                except Exception:
                    pass
            if not set_material_done:
                try:
                    from Cocoa import NSVisualEffectMaterialSidebar

                    effect.setMaterial_(NSVisualEffectMaterialSidebar)
                    set_material_done = True
                except Exception:
                    pass
            if not set_material_done:
                try:
                    from Cocoa import NSVisualEffectMaterialUnderWindowBackground

                    effect.setMaterial_(NSVisualEffectMaterialUnderWindowBackground)
                    set_material_done = True
                except Exception:
                    pass
            # Optionally emphasize the effect (when supported)
            try:
                effect.setEmphasized_(True)
            except Exception:
                pass
            try:
                effect.setAutoresizingMask_(
                    int(NSViewWidthSizable) | int(NSViewHeightSizable)
                )
            except Exception:
                pass
            # Add as the first subview so other controls appear above it
            try:
                content.addSubview_(effect)
                # Ensure it's at back by re-adding others after this point
            except Exception:
                pass
        except Exception:
            pass

        # Search field (taller) with transparent background
        self.search = NSSearchField.alloc().initWithFrame_(
            NSMakeRect(12, h - 48, w - 24, 32)
        )
        self.search.setPlaceholderString_("Search text…")
        self.search.setTarget_(self)
        self.search.setAction_("onSearch:")
        # Visual tweaks: clear background and larger font
        try:
            self.search.setBezeled_(False)
        except Exception:
            pass
        try:
            self.search.setBordered_(False)
        except Exception:
            pass
        try:
            self.search.setDrawsBackground_(False)
        except Exception:
            pass
        try:
            self.search.setBackgroundColor_(NSColor.clearColor())
        except Exception:
            pass
        try:
            self.search.setFont_(NSFont.systemFontOfSize_(16))
        except Exception:
            pass

        # Add a subtle darker, translucent background behind the search field
        try:
            content = self.window.contentView()
            sf = self.search.frame()
            bg = NSView.alloc().initWithFrame_(
                NSMakeRect(
                    sf.origin.x - 2,
                    sf.origin.y - 1,
                    sf.size.width + 4,
                    sf.size.height + 10,
                )
            )
            try:
                bg.setWantsLayer_(True)
                layer = bg.layer()
                # Slightly dark translucent fill
                try:
                    c = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.22)
                    layer.setBackgroundColor_(c.CGColor())
                except Exception:
                    try:
                        from Quartz.CoreGraphics import CGColorCreateGenericRGB

                        layer.setBackgroundColor_(
                            CGColorCreateGenericRGB(0.0, 0.0, 0.0, 0.22)
                        )
                    except Exception:
                        pass
                try:
                    layer.setCornerRadius_(10.0)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                bg.setAutoresizingMask_(int(NSViewWidthSizable))
            except Exception:
                pass
            content.addSubview_(bg)
        except Exception:
            pass
        # Make AppDelegate the editing delegate to intercept Return/Escape/Arrow keys
        try:
            self.search.setDelegate_(self)
        except Exception:
            pass
        self.window.contentView().addSubview_(self.search)
        # handle Enter/Escape like Spotlight
        try:
            self.search.setSendsSearchStringImmediately_(True)
        except Exception:
            pass
        try:
            # focus the search field immediately
            self.window.makeFirstResponder_(self.search)
        except Exception:
            pass

        # Table view
        self.table = KeyboardTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, w - 24, h - 104)
        )
        # Expose owner back-reference for keyboard actions
        try:
            self.table.owner = self
        except Exception:
            pass
        col = NSTableColumn.alloc().initWithIdentifier_("preview")
        col.setTitle_("History")
        col.setWidth_(w - 30)
        self.table.addTableColumn_(col)
        self.table.setDelegate_(self.ds)
        self.table.setDataSource_(self.ds)
        # Double click to copy
        try:
            self.table.setTarget_(self)
            self.table.setDoubleAction_("onCopy:")
        except Exception:
            pass
        # Configure selection behavior and appearance
        try:
            self.table.setAllowsMultipleSelection_(False)
        except Exception:
            pass
        try:
            self.table.setAllowsEmptySelection_(False)
        except Exception:
            pass
        try:
            self.table.setAllowsTypeSelect_(True)
        except Exception:
            pass
        try:
            # NSTableViewSelectionHighlightStyleRegular == 1
            self.table.setSelectionHighlightStyle_(1)
        except Exception:
            pass
        try:
            self.table.setHeaderView_(None)
        except Exception:
            pass
        try:
            self.table.setRowHeight_(64)
            # Add vertical spacing between rows (intercell spacing)
            try:
                # PyObjC accepts a 2-tuple for NSSize
                self.table.setIntercellSpacing_((3, 8))  # (horizontal, vertical)
            except Exception:
                pass
        except Exception:
            pass
        try:
            # Transparent background for table; disable alternating colors to avoid opaque stripes
            self.table.setBackgroundColor_(NSColor.clearColor())
        except Exception:
            pass
        try:
            self.table.setUsesAlternatingRowBackgroundColors_(False)
        except Exception:
            pass

        # Leave an 8px gap under the search field: top reserved = 16 (top) + 32 (search) + 8 (gap) = 56
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(12, 48, w - 24, h - 104)
        )
        try:
            # Transparent scroll view background, so the window translucency shows through
            scroll.setDrawsBackground_(False)
        except Exception:
            pass
        try:
            scroll.setBackgroundColor_(NSColor.clearColor())
        except Exception:
            pass
        # Ensure the clip view (contentView) is also transparent and borderless
        try:
            clip = scroll.contentView()
            try:
                clip.setDrawsBackground_(False)
            except Exception:
                pass
            try:
                clip.setBackgroundColor_(NSColor.clearColor())
            except Exception:
                pass
        except Exception:
            pass
        try:
            from Cocoa import NSNoBorder

            scroll.setBorderType_(NSNoBorder)
        except Exception:
            pass
        # Scrollbar appearance tweaks
        try:
            # Overlay style (thin, floating) scrollers
            from Cocoa import NSScrollerStyleOverlay

            scroll.setScrollerStyle_(NSScrollerStyleOverlay)
        except Exception:
            try:
                scroll.setScrollerStyle_(1)  # Fallback to numeric overlay style
            except Exception:
                pass
        try:
            # Keep scrollers hidden when idle (default on overlay)
            scroll.setAutohidesScrollers_(True)
        except Exception:
            pass
        try:
            scroll.setHasHorizontalScroller_(False)
        except Exception:
            pass
        # Customize vertical scroller knob
        try:
            vs = scroll.verticalScroller()
            if vs is not None:
                try:
                    from Cocoa import NSScrollerKnobStyleLight

                    vs.setKnobStyle_(NSScrollerKnobStyleLight)
                except Exception:
                    try:
                        from Cocoa import NSScrollerKnobStyleDark

                        vs.setKnobStyle_(NSScrollerKnobStyleDark)
                    except Exception:
                        try:
                            vs.setKnobStyle_(2)  # likely Light
                        except Exception:
                            pass
                try:
                    from Cocoa import NSControlSizeSmall

                    vs.setControlSize_(NSControlSizeSmall)
                except Exception:
                    pass
                try:
                    vs.setAlphaValue_(0.9)
                except Exception:
                    pass
        except Exception:
            pass
        scroll.setDocumentView_(self.table)
        scroll.setHasVerticalScroller_(True)
        self.window.contentView().addSubview_(scroll)

        # Focus chain: Tab between search field and table
        try:
            self.search.setNextKeyView_(self.table)
            self.table.setNextKeyView_(self.search)
            self.window.setInitialFirstResponder_(self.search)
        except Exception:
            pass

        # Initial load & default selection for quick Return
        try:
            self.table.reloadData()
            if self.table.numberOfRows() > 0:
                self._select_index(0)
        except Exception:
            pass

        # Buttons (with translucent backgrounds matching search field)
        self.copyBtn = NSButton.alloc().initWithFrame_(NSMakeRect(w - 200, 12, 88, 28))
        self.copyBtn.setTitle_("Copy")
        self.copyBtn.setBezelStyle_(NSBezelStyleRounded)
        try:
            self.copyBtn.setBordered_(False)
        except Exception:
            pass
        try:
            # Better contrast on darker bg
            self.copyBtn.setContentTintColor_(NSColor.whiteColor())
        except Exception:
            pass
        self.copyBtn.setTarget_(self)
        self.copyBtn.setAction_("onCopy:")
        try:
            content = self.window.contentView()
            f = self.copyBtn.frame()
            bg1 = NSView.alloc().initWithFrame_(
                NSMakeRect(
                    f.origin.x - 2, f.origin.y - 2, f.size.width + 4, f.size.height + 4
                )
            )
            try:
                bg1.setWantsLayer_(True)
                layer = bg1.layer()
                c = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.22)
                try:
                    layer.setBackgroundColor_(c.CGColor())
                except Exception:
                    pass
                try:
                    layer.setCornerRadius_(8.0)
                except Exception:
                    pass
            except Exception:
                pass
            content.addSubview_(bg1)
        except Exception:
            pass
        self.window.contentView().addSubview_(self.copyBtn)

        # Settings button
        self.settingsBtn = NSButton.alloc().initWithFrame_(NSMakeRect(12, 12, 100, 28))
        self.settingsBtn.setTitle_("Settings")
        self.settingsBtn.setBezelStyle_(NSBezelStyleRounded)
        try:
            self.settingsBtn.setBordered_(False)
        except Exception:
            pass
        try:
            self.settingsBtn.setContentTintColor_(NSColor.whiteColor())
        except Exception:
            pass
        self.settingsBtn.setTarget_(self)
        self.settingsBtn.setAction_("onOpenSettings:")
        try:
            content = self.window.contentView()
            f = self.settingsBtn.frame()
            bgS = NSView.alloc().initWithFrame_(
                NSMakeRect(
                    f.origin.x - 2, f.origin.y - 2, f.size.width + 4, f.size.height + 4
                )
            )
            try:
                bgS.setWantsLayer_(True)
                layer = bgS.layer()
                c = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.22)
                layer.setBackgroundColor_(c.CGColor())
                layer.setCornerRadius_(8.0)
            except Exception:
                pass
            content.addSubview_(bgS)
        except Exception:
            pass
        self.window.contentView().addSubview_(self.settingsBtn)

        self.closeBtn = NSButton.alloc().initWithFrame_(NSMakeRect(w - 100, 12, 88, 28))
        self.closeBtn.setTitle_("Close")
        self.closeBtn.setBezelStyle_(NSBezelStyleRounded)
        try:
            self.closeBtn.setBordered_(False)
        except Exception:
            pass
        try:
            self.closeBtn.setContentTintColor_(NSColor.whiteColor())
        except Exception:
            pass
        self.closeBtn.setTarget_(self)
        self.closeBtn.setAction_("onClose:")
        try:
            content = self.window.contentView()
            f = self.closeBtn.frame()
            bg2 = NSView.alloc().initWithFrame_(
                NSMakeRect(
                    f.origin.x - 2, f.origin.y - 2, f.size.width + 4, f.size.height + 4
                )
            )
            try:
                bg2.setWantsLayer_(True)
                layer = bg2.layer()
                c = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.22)
                try:
                    layer.setBackgroundColor_(c.CGColor())
                except Exception:
                    pass
                try:
                    layer.setCornerRadius_(8.0)
                except Exception:
                    pass
            except Exception:
                pass
            content.addSubview_(bg2)
        except Exception:
            pass
        self.window.contentView().addSubview_(self.closeBtn)

        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        # Install custom key monitor to handle keyboard input even if responders fail
        self._install_key_monitor()

    # --- Settings window ---
    def onOpenSettings_(self, sender):
        try:
            # Build a simple modal sheet with plugin toggles
            w, h = 420, 280
            sheet = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, w, h), 15, 2, False
            )
            sheet.setTitle_("Settings")
            try:
                sheet.setTitlebarAppearsTransparent_(True)
                sheet.setTitleVisibility_(NSWindowTitleHidden)
            except Exception:
                pass
            try:
                sheet.setOpaque_(False)
                sheet.setBackgroundColor_(
                    NSColor.colorWithCalibratedWhite_alpha_(0, 0.4)
                )
            except Exception:
                pass

            # Header label
            header = NSTextField.alloc().initWithFrame_(
                NSMakeRect(20, h - 40, w - 40, 20)
            )
            header.setStringValue_("Plugins")
            header.setBezeled_(False)
            header.setEditable_(False)
            header.setDrawsBackground_(False)
            header.setBordered_(False)
            sheet.contentView().addSubview_(header)

            # Load current plugin states
            try:
                from Library.plugin import PluginManager as PM

                # Access the shared list via persisted names
                enabled_map = app_settings.get_plugins_enabled()
            except Exception:
                enabled_map = {}

            # Discover plugins in this folder and read each file's NAME without importing the module
            import os, re

            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            entries = []  # list of (key, label)

            def _read_name_from_file(path: str, fallback: str) -> str:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read(4096)  # read first chunk; NAME should be near top
                    m = re.search(r"^\s*NAME\s*=\s*([\"'])(.*?)\1", txt, re.MULTILINE)
                    if m:
                        name = (m.group(2) or "").strip()
                        if name:
                            return name
                except Exception:
                    pass
                return fallback

            try:
                for fname in sorted(os.listdir(plugin_dir)):
                    if not fname.endswith(".py"):
                        continue
                    if fname.startswith("__"):
                        continue
                    key = os.path.splitext(fname)[0]  # storage key (module basename)
                    fallback = key.replace("_", " ").title()
                    label = _read_name_from_file(
                        os.path.join(plugin_dir, fname), fallback
                    )
                    entries.append((key, label))
            except Exception:
                pass

            # Build checkboxes
            self._plugin_checks = []
            start_y = h - 70
            for i, (key, label) in enumerate(entries):
                y = start_y - i * 28
                cb = NSButton.alloc().initWithFrame_(NSMakeRect(20, y, w - 40, 22))
                cb.setButtonType_(3)  # NSSwitch / NSButtonTypeSwitch
                cb.setTitle_(label)
                try:
                    # Backward-compat: check both new key (module name) and old label/title keys
                    state = True
                    if key in enabled_map:
                        state = bool(enabled_map.get(key, True))
                    elif label in enabled_map:
                        state = bool(enabled_map.get(label, True))
                    elif (label.title()) in enabled_map:
                        state = bool(enabled_map.get(label.title(), True))
                    cb.setState_(1 if state else 0)
                except Exception:
                    pass
                # store both module key and display label for saving
                self._plugin_checks.append((key, label, cb))
                sheet.contentView().addSubview_(cb)

            # Save & Close button
            saveBtn = NSButton.alloc().initWithFrame_(NSMakeRect(w - 100, 12, 80, 28))
            saveBtn.setTitle_("Save")
            saveBtn.setBezelStyle_(NSBezelStyleRounded)
            saveBtn.setTarget_(self)
            saveBtn.setAction_("onSettingsSave:")
            sheet.contentView().addSubview_(saveBtn)

            self._settingsSheet = sheet
            try:
                self.window.beginSheet_completionHandler_(sheet, None)
            except Exception:
                sheet.makeKeyAndOrderFront_(None)
        except Exception:
            pass

    def onSettingsSave_(self, sender):
        try:
            enabled_map = {}
            # Write by display name (label) to match main.py, and also by module key for back-compat
            for entry in getattr(self, "_plugin_checks", []):
                try:
                    if len(entry) == 3:
                        key, label, cb = entry
                    else:
                        # older tuple (name, cb) fallback
                        key, cb = entry
                        label = key.replace("_", " ").title()
                    state = bool(cb.state())
                except Exception:
                    state = True
                try:
                    enabled_map[label] = state
                    enabled_map[key] = state
                except Exception:
                    pass
            # Persist (merged into settings.json)
            app_settings.set_plugins_enabled(enabled_map)
        except Exception:
            pass
        try:
            if getattr(self, "_settingsSheet", None):
                self.window.endSheet_(self._settingsSheet)
                self._settingsSheet.orderOut_(None)
                self._settingsSheet = None
        except Exception:
            pass

    def onSearch_(self, sender):
        self.ds.filter_(sender.stringValue())
        self.table.reloadData()
        # select first row for quick Enter
        try:
            if self.table.numberOfRows() > 0:
                from Cocoa import NSIndexSet

                self.table.selectRowIndexes_byExtendingSelection_(
                    NSIndexSet.indexSetWithIndex_(0), False
                )
        except Exception:
            pass

    def onCopy_(self, sender):
        sel = self.table.selectedRow()
        if sel < 0 or sel >= len(self.ds.filtered):
            return
        item = self.ds.filtered[sel]
        t = item.get("type")
        if t == "text":
            mcb.MacClipboard.set_text(item.get("text") or "")
        elif t == "image":
            path = item.get("image_path")
            if path and os.path.exists(path):
                from PIL import Image

                img = Image.open(path).convert("RGBA")
                mcb.MacClipboard.set_image(img)
                # マーカーを付与（この画像は GUI からのコピー）
                try:
                    mcb.MacClipboard.set_source_marker("GUI_IMAGE")
                except Exception:
                    pass
        # Optional: paste back then close
        try:
            self._maybe_paste_after_copy()
        except Exception:
            pass
        self.onClose_(sender)

    # Allow Return/Escape shortcuts
    def control_textView_doCommandBySelector_(self, control, textView, selector):
        # Return key
        if str(selector) == "insertNewline:":
            self.onCopy_(control)
            return True
        # Escape key
        if str(selector) == "cancelOperation:":
            self.onClose_(control)
            return True
        # Up/Down arrows to navigate selection like Spotlight
        if str(selector) == "moveUp:":
            self._move_selection(-1)
            return True
        if str(selector) == "moveDown:":
            self._move_selection(1)
            return True
        if str(selector) == "moveToBeginningOfDocument:":
            self._select_index(0)
            return True
        if str(selector) == "moveToEndOfDocument:":
            last = max(0, self.table.numberOfRows() - 1)
            self._select_index(last)
            return True
        return False

    # Live search: filter on each keystroke in NSSearchField
    def controlTextDidChange_(self, notification):
        try:
            sender = notification.object()
            if sender is self.search:
                self.onSearch_(self.search)
        except Exception:
            pass

    def _move_selection(self, delta: int):
        try:
            rows = self.table.numberOfRows()
            if rows <= 0:
                return
            cur = self.table.selectedRow()
            if cur < 0:
                cur = 0 if delta >= 0 else rows - 1
            idx = max(0, min(rows - 1, cur + int(delta)))
            self._select_index(idx)
        except Exception:
            pass

    def _select_index(self, idx: int):
        try:
            from Cocoa import NSIndexSet

            rows = self.table.numberOfRows()
            if rows <= 0:
                return
            idx = max(0, min(rows - 1, int(idx)))
            self.table.selectRowIndexes_byExtendingSelection_(
                NSIndexSet.indexSetWithIndex_(idx), False
            )
            self.table.scrollRowToVisible_(idx)
        except Exception:
            pass

    # Helpers to determine current focus owner when firstResponder is a field editor
    def _responder_in_search(self, responder):
        try:
            if responder is None:
                return False
            if responder is self.search:
                return True
            # Field editor case
            if isinstance(responder, NSTextView):
                # Its delegate should be our search field when editing it
                try:
                    return responder.delegate() is self.search
                except Exception:
                    return False
            return False
        except Exception:
            return False

    def _responder_in_table(self, responder):
        try:
            if responder is None:
                return False
            if responder is self.table:
                return True
            # When a cell view is focused, its enclosing table should be our table
            try:
                v = responder
                # Walk up the view hierarchy a few steps
                for _ in range(5):
                    if v is None:
                        break
                    if v is self.table:
                        return True
                    v = getattr(v, "superview", lambda: None)()
            except Exception:
                pass
            return False
        except Exception:
            return False

    def onClose_(self, sender):
        # Remove key monitor
        try:
            if getattr(self, "_keyMonitor", None):
                NSEvent.removeMonitor_(self._keyMonitor)
                self._keyMonitor = None
        except Exception:
            pass
        # Remove distributed notification observer
        try:
            if getattr(self, "_distCenter", None):
                self._distCenter.removeObserver_(self)
        except Exception:
            pass
        NSApp.terminate_(self)

    # Terminate when an external close request is received
    def onExternalClose_(self, notification):
        try:
            self.onClose_(self)
        except Exception:
            try:
                NSApp.terminate_(self)
            except Exception:
                pass

    def _maybe_paste_after_copy(self):
        if not getattr(self, "autoPaste", True):
            return
        # Reactivate previous app
        try:
            if getattr(self, "prevApp", None):
                try:
                    self.prevApp.activateWithOptions_(0)
                except Exception:
                    pass
        except Exception:
            pass
        # Small delay to focus
        try:
            time.sleep(0.08)
        except Exception:
            pass
        # Send Cmd+V
        try:
            try:
                from Quartz import CoreGraphics as CG
            except Exception:
                import Quartz as CG  # type: ignore
            vkey = 9  # 'v'
            ev_down = CG.CGEventCreateKeyboardEvent(None, vkey, True)
            CG.CGEventSetFlags(ev_down, CG.kCGEventFlagMaskCommand)
            CG.CGEventPost(CG.kCGHIDEventTap, ev_down)
            ev_up = CG.CGEventCreateKeyboardEvent(None, vkey, False)
            CG.CGEventSetFlags(ev_up, CG.kCGEventFlagMaskCommand)
            CG.CGEventPost(CG.kCGHIDEventTap, ev_up)
        except Exception:
            pass

    # --- Custom keyboard monitor (independent of native responders) ---
    def _install_key_monitor(self):
        try:
            try:
                from Cocoa import NSEventMaskKeyDown

                mask = NSEventMaskKeyDown
            except Exception:
                from Cocoa import NSKeyDownMask as mask

            def _handler(event):
                try:
                    # Only handle when our window is active
                    if not self.window or not self.window.isKeyWindow():
                        return event

                    kc = int(event.keyCode())

                    # Enter/Return
                    if kc in (36, 76):
                        self.onCopy_(self)
                        return None
                    # Escape
                    if kc == 53:
                        self.onClose_(self)
                        return None
                    # Up / Down arrows
                    if kc == 126:  # Up
                        self._move_selection(-1)
                        return None
                    if kc in (125, 48):  # Down
                        self._move_selection(1)
                        return None
                    # Home/End equivalent (cmd+up/down are handled elsewhere; here map to begin/end)
                    if kc == 115:  # Home
                        self._select_index(0)
                        return None
                    if kc == 119:  # End
                        last = max(0, self.table.numberOfRows() - 1)
                        self._select_index(last)
                        return None
                    # Backspace/Delete
                    if kc in (51, 117):
                        try:
                            cur = str(self.search.stringValue() or "")
                            if len(cur) > 0:
                                cur = cur[:-1]
                            self.search.setStringValue_(cur)
                            self.onSearch_(self.search)
                        except Exception:
                            pass
                        return None

                    # Append printable characters to search
                    try:
                        chars = event.charactersIgnoringModifiers() or ""
                        if len(chars) == 1 and 32 <= ord(chars) < 127:
                            cur = str(self.search.stringValue() or "") + chars
                            self.search.setStringValue_(cur)
                            self.onSearch_(self.search)
                            return None
                    except Exception:
                        pass

                except Exception:
                    pass
                # Fallback: let the system process it
                return event

            self._keyMonitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                mask, _handler
            )
        except Exception:
            pass


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    app.run()


if __name__ == "__main__":
    main()

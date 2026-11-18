import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Keyboard} from 'resource:///org/gnome/shell/ui/keyboard.js';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class TouchGestures extends Extension {
    enable() {
        this._pagers = new Map();
        this._injections = new InjectionManager();
        const extension = this;
        this._injections.overrideMethod(Keyboard.prototype, '_setupKeyboard', original => function (...args) {
            const result = original.apply(this, args);
            extension._watch(this._emojiSelection?._emojiPager);
            return result;
        });
        this._watch(Main.keyboard.keyboardActor?._emojiSelection?._emojiPager);
    }
    _watch(pager) {
        if (!pager || this._pagers.has(pager))
            return;
        const sync = () => {
            if (pager._swipeTracker)
                pager._swipeTracker.enabled = pager.visible && pager.mapped;
        };
        const ids = [pager.connect('notify::mapped', sync), pager.connect('notify::visible', sync)];
        ids.push(pager.connect('destroy', () => this._pagers.delete(pager)));
        this._pagers.set(pager, ids);
        sync();
    }
    disable() {
        this._injections?.clear();
        for (const [pager, ids] of this._pagers) {
            for (const id of ids)
                pager.disconnect(id);
            if (pager._swipeTracker)
                pager._swipeTracker.enabled = pager.visible;
        }
        this._pagers.clear();
    }
}

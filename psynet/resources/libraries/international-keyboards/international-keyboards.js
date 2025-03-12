const AVAILABLE_KEYS = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8', 'Digit9', 'Digit0', 'Minus', 'Equal', 'KeyQ', 'KeyW', 'KeyE', 'KeyR', 'KeyT', 'KeyY', 'KeyU', 'KeyI', 'KeyO', 'KeyP', 'BracketLeft', 'BracketRight', 'KeyA', 'KeyS', 'KeyD', 'KeyF', 'KeyG', 'KeyH', 'KeyJ', 'KeyK', 'KeyL', 'Semicolon', 'Quote', 'Backquote', 'Backslash', 'KeyZ', 'KeyX', 'KeyC', 'KeyV', 'KeyB', 'KeyN', 'KeyM', 'Comma', 'Period', 'Slash'];
const KEYBOARD_TYPES = ['ANSI', 'ISO', 'JIS'];
const CSS_STYLES = ['inverted', 'default', 'apple'];

/* ========================================================================
 * international-keyboards - v0.12.1 (Improved)
 * ========================================================================
 * Enhancements:
 * - Modernized AJAX requests with fetch
 * - Improved error handling
 * - Optimized event handling
 * - Cleaner DOM manipulation
 * ========================================================================
 */

(function (window, factory) {
    if (typeof define === 'function' && define.amd) {
        define(['jquery'], function (jQuery) {
            return window.InternationalKeyboard = factory(jQuery);
        });
    } else if (typeof exports === 'object') {
        module.exports = factory(require('jquery'));
    } else {
        window.InternationalKeyboard = factory(window.jQuery);
    }
})(window, function ($) {
    "use strict";

    class InternationalKeyboard {
        constructor(options) {
            this._options = $.extend({
                keyboardID: undefined,
                containerID: 'keyboard',
                highlightedKeys: [],
                keyboardType: 'ANSI',
                addLatinKeys: false,
                showKeys: AVAILABLE_KEYS,
                cssStyle: 'inverted'
            }, options);
            this.validateOptions();
            this.createKeyboard();
        }

        validateOptions() {
            const {keyboardType, cssStyle} = this._options;

            if (!KEYBOARD_TYPES.includes(keyboardType)) {
                throw new Error(`Unsupported keyboard type: ${keyboardType}`);
            }
            if (!CSS_STYLES.includes(cssStyle)) {
                throw new Error(`Unsupported CSS style: ${cssStyle}`);
            }
        }

        async createKeyboard() {
            await this.loadAllLayouts();
            await this.loadKeyboard(this._options.keyboardType, this._options.containerID, this._options.cssStyle);
            await this.insertKeyLabels(this._options.keyboardID, this._options.cssStyle);
            await this.highlightKeys(this._options.highlightedKeys);
        }

        async highlightKeys(keys) {
            keys.forEach(key => this.highlight(key));
        }

        async loadAllLayouts() {
            const response = await fetch(`/static/international-keyboards/keyboard_layouts.json`);
            if (!response.ok) throw new Error(`Failed to load key data (${response.status})`);
            this.keyboardLayouts = await response.json();
        }

        async loadKeyboard(keyboardType, containerID) {
            try {
                const response = await fetch(`/static/international-keyboards/${keyboardType}.svg`);
                if (!response.ok) throw new Error(`Failed to load keyboard SVG (${response.status})`);

                const svgText = await response.text();
                document.getElementById(containerID).innerHTML = svgText;
            } catch (error) {
                console.error("Error loading keyboard SVG:", error);
            }
        }

        async insertKeyLabels(keyboardID, cssStyle) {
            try {
                document.querySelectorAll('svg path').forEach(path => path.classList.add('key', cssStyle));
                const data = this.keyboardLayouts[keyboardID];
                Object.entries(data).forEach(([key, value]) => {
                    const path = document.getElementById(key);
                    if (!path) return console.warn(`Key not found: ${key}`);

                    if (!this._options.showKeys.includes(key)) return;

                    const bbox = path.getBBox();
                    const keyText = value['lower'].toUpperCase();
                    const parent = path.parentNode;

                    const textElement = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    textElement.setAttribute("x", bbox.x + bbox.width / 2);
                    textElement.setAttribute("y", bbox.y + bbox.height / 2 + 20);
                    textElement.setAttribute("text-anchor", "middle");
                    textElement.setAttribute("class", `keyLabel ${cssStyle}`);
                    textElement.setAttribute("id", `label-${key}`);
                    textElement.textContent = keyText;
                    parent.appendChild(textElement);
                });
            } catch (error) {
                console.error("Error loading key data:", error);
            }
        }

        press(key, duration = 300) {
            this.hold(key);
            setTimeout(() => this.release(key), duration);
        }

        getKey(key) {
            return document.getElementById(key) || console.warn(`Key not found: ${key}`);
        }

        addToClassList(key, className) {
            const element = this.getKey(key);
            if (element) element.classList.add(className);
        }

        hold(key, className = 'press') {
            this.addToClassList(key, className);
            this.addToClassList(`label-${key}`, className);
        }

        removeFromClassList(key, className) {
            const element = this.getKey(key);
            if (element) element.classList.remove(className);
        }

        release(key, className = 'press') {
            this.removeFromClassList(key, className);
            this.removeFromClassList(`label-${key}`, className);
        }

        highlight(key) {
            this.hold(key, 'highlight');
        }
    }

    return InternationalKeyboard;
});

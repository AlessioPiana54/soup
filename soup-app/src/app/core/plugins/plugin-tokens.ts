import { InjectionToken } from '@angular/core';

import { InputFormatPlugin } from '../input/input-format-plugin';

/**
 * Multi-provider token every registered InputFormatPlugin is attached
 * to. Injecting this token yields the array of every format contributed
 * by every plugin passed to provideSoupPlugins() across the app.
 */
export const INPUT_FORMAT_PLUGINS = new InjectionToken<InputFormatPlugin>('INPUT_FORMAT_PLUGINS');

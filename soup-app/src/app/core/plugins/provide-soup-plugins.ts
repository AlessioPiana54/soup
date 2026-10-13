import { EnvironmentProviders, makeEnvironmentProviders, Provider } from '@angular/core';

import { INPUT_FORMAT_PLUGINS } from './plugin-tokens';
import { SoupFrontendPlugin } from './soup-frontend-plugin';

/**
 * provideSoupPlugins - registers every contribution of the given plugins
 * with the app's environment injector (the Angular-side equivalent of
 * the backend's PluginManager.load()). Call once per plugin in
 * app.config.ts's `providers` array.
 */
export function provideSoupPlugins(...plugins: SoupFrontendPlugin[]): EnvironmentProviders {
  const providers: Provider[] = [];

  for (const plugin of plugins) {
    for (const inputFormat of plugin.inputFormats ?? []) {
      providers.push({ provide: INPUT_FORMAT_PLUGINS, useValue: inputFormat, multi: true });
    }
  }

  return makeEnvironmentProviders(providers);
}

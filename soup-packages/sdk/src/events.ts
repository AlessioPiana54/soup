/**
 * The standard DOM events a package element sends to the host. They bubble
 * and cross shadow roots, so they can be dispatched from anywhere inside
 * the element. The host listens on the element it mounted.
 */

import { FormValues, NotifyLevel } from './types';

export const SOUP_EVENTS = {
  /** detail: {svg} - the SVG preview of the object for the workspace. */
  thumbnail: 'soup-thumbnail',
  /** detail: {id} - open another object of the workspace. */
  openObject: 'soup-open-object',
  /** detail: {message, level} - show a notification. */
  notify: 'soup-notify',
  /** detail: {value} - a configuration element changed the importer options. */
  configChange: 'soup-config-change'
} as const;

export type SoupEventName = (typeof SOUP_EVENTS)[keyof typeof SOUP_EVENTS];

export interface ThumbnailDetail {
  svg: string;
}

export interface OpenObjectDetail {
  id: string;
}

export interface NotifyDetail {
  message: string;
  level: NotifyLevel;
}

export interface ConfigChangeDetail {
  value: FormValues;
}

export interface SoupEventDetails {
  'soup-thumbnail': ThumbnailDetail;
  'soup-open-object': OpenObjectDetail;
  'soup-notify': NotifyDetail;
  'soup-config-change': ConfigChangeDetail;
}

/** Dispatch a standard event from `target` (bubbling, composed). */
export function dispatchSoupEvent<K extends SoupEventName>(target: EventTarget, name: K, detail: SoupEventDetails[K]): boolean {
  return target.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}

/** The detail of a standard event, typed by its name. */
export function soupEventDetail<K extends SoupEventName>(event: Event, _name: K): SoupEventDetails[K] {
  return (event as CustomEvent<SoupEventDetails[K]>).detail;
}

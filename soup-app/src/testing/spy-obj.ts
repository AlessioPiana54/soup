import { type Mock, vi } from 'vitest';

/** The methods of T as Vitest mocks, like a jasmine.SpyObj<T>. */
export type SpyObj<T> = {
  [K in keyof T]: T[K] extends (...args: never[]) => unknown ? Mock<T[K]> : T[K];
};

/** jasmine.createSpyObj for Vitest: an object whose `methods` are vi.fn() (returning undefined until mocked). */
export function createSpyObj<T>(methods: readonly (keyof T & string)[]): SpyObj<T> {
  return Object.fromEntries(methods.map((method) => [method, vi.fn()])) as unknown as SpyObj<T>;
}

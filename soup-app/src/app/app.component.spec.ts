import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, provideRouter, Route, Router, ViewTransitionInfo } from '@angular/router';

import { createSpyObj } from '../testing/spy-obj';
import { AppComponent } from './app.component';
import { changesPage, PAGE_TRANSITIONS } from './page-transitions';

@Component({ selector: 'app-first-page', standalone: true, template: '<p>first</p>' })
class FirstPageComponent {}

@Component({ selector: 'app-second-page', standalone: true, template: '<p>second</p>' })
class SecondPageComponent {}

const FIRST: Route = { path: 'first', component: FirstPageComponent };
const SECOND: Route = { path: 'second', component: SecondPageComponent };
const OBJECT: Route = { path: 'o/:id', component: SecondPageComponent };

/** A snapshot whose deepest route (the page) is `page`. */
function snapshot(page: Route | null): ActivatedRouteSnapshot {
  const child = { routeConfig: page, firstChild: null } as unknown as ActivatedRouteSnapshot;
  return { routeConfig: null, firstChild: child } as unknown as ActivatedRouteSnapshot;
}

describe('AppComponent', () => {
  let fixture: ComponentFixture<AppComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      // No view transitions here: jsdom has no document.startViewTransition (the e2e run them in the
      // browser); PAGE_TRANSITIONS is tested below.
      providers: [provideRouter([FIRST, SECOND]), provideHttpClient(), provideHttpClientTesting()]
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  async function navigate(url: string): Promise<void> {
    await router.navigateByUrl(url);
    fixture.detectChanges();
    await fixture.whenStable();
  }

  it('should create the app', () => {
    expect(fixture.componentInstance.title).toEqual('soup-app');
  });

  it('keeps the page scrollable at the change detections after a navigation', async () => {
    await navigate('/first');
    await navigate('/second');

    fixture.detectChanges();

    expect(document.body.style.overflow).not.toBe('hidden');
    expect(getComputedStyle(document.body).overflow).not.toBe('hidden');
    expect(fixture.nativeElement.querySelector('.content app-second-page')).not.toBeNull();
  });

  it('names the content for the view transitions only while one runs (styles.scss)', () => {
    const content = fixture.nativeElement.querySelector('.content') as HTMLElement;

    expect(getComputedStyle(content).getPropertyValue('view-transition-name')).toBe('none');
  });
});

describe('PAGE_TRANSITIONS', () => {
  it('a navigation to another page changes it, one that keeps the route (only its parameters) does not', () => {
    expect(changesPage(snapshot(FIRST), snapshot(SECOND))).toBe(true);
    expect(changesPage(snapshot(null), snapshot(FIRST))).toBe(true);
    expect(changesPage(snapshot(OBJECT), snapshot(OBJECT))).toBe(false);
  });

  it('skips the transition of a navigation that keeps its page', () => {
    const transition = createSpyObj<ViewTransition>(['skipTransition']);
    const created = (from: Route, to: Route) =>
      PAGE_TRANSITIONS.onViewTransitionCreated!({ transition, from: snapshot(from), to: snapshot(to) } as ViewTransitionInfo);

    created(FIRST, SECOND);
    expect(transition.skipTransition).not.toHaveBeenCalled();

    created(OBJECT, OBJECT);
    expect(transition.skipTransition).toHaveBeenCalledTimes(1);
  });
});

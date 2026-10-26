import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';

import { AppComponent } from './app.component';

@Component({ selector: 'app-first-page', standalone: true, template: '<p>first</p>' })
class FirstPageComponent {}

@Component({ selector: 'app-second-page', standalone: true, template: '<p>second</p>' })
class SecondPageComponent {}

describe('AppComponent', () => {
  let fixture: ComponentFixture<AppComponent>;
  let router: Router;
  // body.style.overflow seen when each route animation ends, before it is restored
  let overflowAtDone: string[];

  beforeEach(async () => {
    overflowAtDone = [];
    const restore = AppComponent.prototype.onAnimationDone;
    spyOn(AppComponent.prototype, 'onAnimationDone').and.callFake(function (this: AppComponent) {
      overflowAtDone.push(document.body.style.overflow);
      restore.call(this);
    });

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideRouter([
          { path: 'first', component: FirstPageComponent },
          { path: 'second', component: SecondPageComponent }
        ]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  afterEach(() => {
    document.body.style.removeProperty('overflow');
  });

  async function navigate(url: string): Promise<void> {
    await router.navigateByUrl(url);
    fixture.detectChanges();
    await fixture.whenStable();
  }

  it('should create the app', () => {
    expect(fixture.componentInstance.title).toEqual('soup-app');
  });

  it('hides the overflow of the body only while the route animation runs', async () => {
    await navigate('/first');
    await navigate('/second');

    expect(overflowAtDone.length).toBeGreaterThan(0);
    expect(overflowAtDone.every((value) => value === 'hidden')).toBeTrue();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('keeps the page scrollable at the change detections after a navigation', async () => {
    await navigate('/first');

    fixture.detectChanges();
    fixture.detectChanges();

    expect(document.body.style.overflow).not.toBe('hidden');
    expect(getComputedStyle(document.body).overflow).not.toBe('hidden');
  });

  it('prepareRoute has no side effects', () => {
    const outlet = { isActivated: false } as never;

    expect(fixture.componentInstance.prepareRoute(outlet)).toBe('');
    expect(document.body.style.overflow).not.toBe('hidden');
  });
});

import { ActivatedRouteSnapshot, ViewTransitionInfo, ViewTransitionsFeatureOptions } from '@angular/router';

/** The deepest route of a snapshot: the page shown. */
function pageOf(route: ActivatedRouteSnapshot): ActivatedRouteSnapshot {
  let page = route;
  while (page.firstChild) page = page.firstChild;
  return page;
}

/**
 * Whether a navigation changes the page: false when it keeps the same route
 * (only its parameters change, e.g. /o/:id to another object), whose page
 * the router reuses.
 */
export function changesPage(from: ActivatedRouteSnapshot, to: ActivatedRouteSnapshot): boolean {
  return pageOf(from).routeConfig !== pageOf(to).routeConfig;
}

/**
 * The page changes as View Transitions of the router (the slide is in
 * styles.scss: the new page enters from the right while the old one leaves
 * to the left). A navigation that keeps its page does not slide.
 */
export const PAGE_TRANSITIONS: ViewTransitionsFeatureOptions = {
  onViewTransitionCreated: ({ transition, from, to }: ViewTransitionInfo) => {
    if (!changesPage(from, to)) transition.skipTransition();
  }
};

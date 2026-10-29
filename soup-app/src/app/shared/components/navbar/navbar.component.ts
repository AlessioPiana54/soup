import { Component } from '@angular/core';
import { Router } from '@angular/router';

/**
 * Navigation bar component
 * @version 1.0
 * @since 1.0.0
 * @author Alessio Giacché
 */
@Component({
  selector: 'app-navbar',
  imports: [],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.scss'
})
export class NavbarComponent {
  /**
   * Constructor for NavbarComponent component
   * @param router the Router
   */
  constructor(private router: Router) {}

  /**
   * Navigate to the home page
   */
  public goToHome(): void {
    this.router.navigate(['/welcome']);
  }

  /**
   * Go to a page of the workspace (/workspace, /import, /packages)
   * @param path the path of the page
   */
  public goTo(path: string): void {
    this.router.navigate([path]);
  }

  /**
   * Return true if the user stay in the welcome
   * page
   */
  public isWelcomePage(): boolean {
    return this.router.url === '/welcome';
  }
}

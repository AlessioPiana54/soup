import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { FooterComponent } from './shared/components/footer/footer.component';
import { NavbarComponent } from './shared/components/navbar/navbar.component';
import { GenericModalComponent } from './shared/components/s-modals/s-generic-modal/s-generic-modal.component';
import { SToastComponent } from './shared/components/s-toast/s-toast.component';

/**
 * Main application component
 * @version 1.0
 * @since 1.0.0
 * @author Alessio Giacché
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, NavbarComponent, FooterComponent, SToastComponent, GenericModalComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  // Application title
  public title = 'soup-app';
}

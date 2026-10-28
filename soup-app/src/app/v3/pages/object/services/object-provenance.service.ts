import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { ObjectRef } from '../../../../core/v3/v3.models';
import { V3ApiService } from '../../../../core/v3/v3-api.service';
import { findNode, flatten } from '../../workspace/workspace-tree';

interface Provenance {
  parents: ObjectRef[];
  children: ObjectRef[];
}

/** Where an object comes from and what was derived from it, read from the workspace tree. */
@Injectable({
  providedIn: 'root'
})
export class ObjectProvenanceService {
  /**
   * Constructor for ObjectProvenanceService service
   * @param api the V3ApiService service
   */
  constructor(private api: V3ApiService) {}

  public of(object: ObjectRef): Observable<Provenance> {
    return this.api.objects().pipe(
      map((nodes) => {
        const all = flatten(nodes).map((node) => node.object);
        const parents = object.parents.map((id) => all.find((item) => item.id === id)).filter((item): item is ObjectRef => !!item);
        const node = findNode(nodes, object.id);
        return { parents, children: node ? node.children.map((child) => child.object) : [] };
      })
    );
  }
}

// Parametric 3 mL model, adapted from render/scene.html. Dimensions in millimetres.
// Label: graph Asset:inbox/labels/BPC-157-10mg_label.png, unchanged print artwork.
export function createVial(THREE, labelTex) {
const vial = new THREE.Group();
const VIAL_ML = 3, AMBER = false, CAKE = '#FBFBF9', U_CENTER = 0.44;
const SEAL = { color: '#C9CDD2', rough: 0.3 };
const ISO = VIAL_ML >= 5
  ? { d1: 22, d2: 20, d3: 16.5, d4: 12.6, h1: 40, yShoulder: 29.2, shR: 2.4, yNeck: 32.4, flangeH: 3.4, r1: 3.5, stopperH: 1.8, btnH: 3.2, cakeH: 12, labelH: 19 }
  : { d1: 16, d2: 13, d3: 10.5, d4: 7.0, h1: 35, yShoulder: 25.0, shR: 1.8, yNeck: 27.6, flangeH: 3.0, r1: 2.5, stopperH: 1.4, btnH: 2.8, cakeH: 10, labelH: 17 };
const Rb = ISO.d1 / 2, Rf = ISO.d2 / 2, Rn = ISO.d3 / 2, Rbore = ISO.d4 / 2, Ri = Rb - 1.0;
const yFlange = ISO.h1 - ISO.flangeH;

const g = [];
g.push(new THREE.Vector2(0.001, 0.45), new THREE.Vector2(Rb - ISO.r1 - 0.8, 0.05), new THREE.Vector2(Rb - ISO.r1, 0));
for (let i = 1; i <= 10; i++) { const a = (i / 10) * Math.PI / 2;           // heel
  g.push(new THREE.Vector2(Rb - ISO.r1 + ISO.r1 * Math.sin(a), ISO.r1 - ISO.r1 * Math.cos(a))); }
g.push(new THREE.Vector2(Rb, ISO.yShoulder));                               // straight body
const cx = Rb - ISO.shR;                                                     // tight shoulder arc
for (let i = 1; i <= 10; i++) { const a = (i / 10) * THREE.MathUtils.degToRad(58);
  g.push(new THREE.Vector2(cx + ISO.shR * Math.cos(a), ISO.yShoulder + ISO.shR * Math.sin(a))); }
const last = g[g.length - 1];
g.push(new THREE.Vector2(Rn + 0.45, ISO.yNeck - 0.35));                     // short slope
for (let i = 1; i <= 5; i++) { const t = i / 5;                            // concave fillet into the neck
  g.push(new THREE.Vector2(Rn + 0.45 * (1 - Math.sin(t * Math.PI / 2)), ISO.yNeck - 0.35 + 0.35 * t)); }
g.push(new THREE.Vector2(Rn, yFlange - 0.1));                               // neck
g.push(new THREE.Vector2(Rn + 0.3, yFlange + 0.12), new THREE.Vector2(Rf - 0.3, yFlange + 0.45), new THREE.Vector2(Rf, yFlange + 0.85));
g.push(new THREE.Vector2(Rf, ISO.h1 - 0.4), new THREE.Vector2(Rf - 0.4, ISO.h1), new THREE.Vector2(Rbore, ISO.h1), new THREE.Vector2(0.001, ISO.h1));
const glass = new THREE.Mesh(new THREE.LatheGeometry(g, 192), new THREE.MeshPhysicalMaterial({
  color: AMBER ? new THREE.Color('#E2A45E') : 0xffffff, metalness: 0, roughness: 0.0, transmission: 1, thickness: AMBER ? 1.3 : 1.2, ior: 1.52, dispersion: 0.15,
  specularIntensity: 1, envMapIntensity: 1.3,
  attenuationColor: new THREE.Color(AMBER ? '#7E3F0B' : '#E2F0EC'), attenuationDistance: AMBER ? 3.8 : 45 }));   // amber = light-protective brown glass
glass.castShadow = true; vial.add(glass);

// lyophilized cake: bright white, matte, tall, slightly shrunk from the wall, uneven top
const cakeH = ISO.cakeH, cakeR = Ri - 0.2, cakeY0 = 0.75;
const cakeGeo = new THREE.CylinderGeometry(cakeR, cakeR, cakeH, 96, 10, false);
const cpos = cakeGeo.attributes.position;
for (let i = 0; i < cpos.count; i++) {
  const x = cpos.getX(i), y = cpos.getY(i), z = cpos.getZ(i), ang = Math.atan2(z, x), rr = Math.hypot(x, z);
  if (y > cakeH / 2 - 0.01) cpos.setY(i, y + 0.4 * Math.sin(ang * 3 + rr) * (rr / cakeR) - 0.3 * (rr / cakeR) ** 2);
  else if (rr > cakeR - 0.01) { const k = 1 + 0.015 * Math.sin(ang * 13 + y * 2.3) * Math.sin(y * 1.7); cpos.setX(i, x * k); cpos.setZ(i, z * k); }
}
cakeGeo.computeVertexNormals();
const cake = new THREE.Mesh(cakeGeo, new THREE.MeshStandardMaterial({ color: CAKE, roughness: 1 }));
cake.position.y = cakeY0 + cakeH / 2; vial.add(cake);

// freeze-drying stopper: dark grey rubber plug in the neck bore with two vent slots, flange on the glass top
const rubber = new THREE.MeshStandardMaterial({ color: '#3E4147', roughness: 0.7 });
const plugTop = ISO.h1, plugSolid = VIAL_ML >= 5 ? 6.2 : 5.0, legLen = VIAL_ML >= 5 ? 3.4 : 2.6;   // solid plug shows below the seal, then short legs
const solid = new THREE.Mesh(new THREE.CylinderGeometry(Rbore - 0.03, Rbore - 0.03, plugSolid, 64), rubber);
solid.position.y = plugTop - plugSolid / 2; vial.add(solid);
for (const t0 of [THREE.MathUtils.degToRad(10), THREE.MathUtils.degToRad(190)]) {   // two legs, 160° each: narrow vent slots front and back
  const leg = new THREE.Mesh(new THREE.CylinderGeometry(Rbore - 0.05, Rbore - 0.25, legLen, 48, 1, false, t0, THREE.MathUtils.degToRad(160)), rubber);
  leg.position.y = plugTop - plugSolid - legLen / 2; vial.add(leg);
}
const flangeRub = new THREE.Mesh(new THREE.CylinderGeometry(Rf - 0.2, Rf - 0.2, ISO.stopperH, 96), rubber);
flangeRub.position.y = ISO.h1 + ISO.stopperH / 2; vial.add(flangeRub);

// aluminium seal: short band, rolled under the flange
const sealTop = ISO.h1 + ISO.stopperH + 0.2;
const sp = [new THREE.Vector2(Rn + 0.15, yFlange - 0.15), new THREE.Vector2(Rn + 0.55, yFlange - 0.02), new THREE.Vector2(Rf - 0.05, yFlange + 0.32),
  new THREE.Vector2(Rf + 0.26, yFlange + 0.85), new THREE.Vector2(Rf + 0.28, sealTop - 0.28), new THREE.Vector2(Rf + 0.05, sealTop),
  new THREE.Vector2(Rf - 1.4, sealTop), new THREE.Vector2(Rf - 1.4, sealTop - 0.2)];
const sealGeo = new THREE.LatheGeometry(sp, 180);
const spos = sealGeo.attributes.position;                                    // crimp pleats where the skirt is rolled under
for (let i = 0; i < spos.count; i++) { const y = spos.getY(i); if (y < yFlange + 0.9) {
  const x = spos.getX(i), z = spos.getZ(i), ang = Math.atan2(z, x), k = 1 + 0.018 * Math.max(0, Math.cos(ang * 22));
  spos.setX(i, x * k); spos.setZ(i, z * k); } }
sealGeo.computeVertexNormals();
const seal = new THREE.Mesh(sealGeo, new THREE.MeshPhysicalMaterial({ color: SEAL.color, metalness: 1, roughness: SEAL.rough, anisotropy: 0.6, envMapIntensity: 0.8, side: THREE.DoubleSide }));
seal.castShadow = true; vial.add(seal);

// flip-off button: thin, matte, slightly wider than the seal, rounded edge, shallow recess
const Rbtn = Rf + 0.45, bt = sealTop + ISO.btnH;
const bp = [new THREE.Vector2(0.001, sealTop + 0.04), new THREE.Vector2(Rbtn - 0.35, sealTop + 0.04)];
for (let i = 0; i <= 6; i++) { const a = -Math.PI / 2 + (i / 6) * Math.PI / 2;    // rounded lower edge
  bp.push(new THREE.Vector2(Rbtn - 0.35 + 0.35 * Math.cos(a), sealTop + 0.39 + 0.35 * Math.sin(a))); }
for (let i = 0; i <= 8; i++) { const a = (i / 8) * Math.PI / 2;                    // rounded upper edge
  bp.push(new THREE.Vector2(Rbtn - 0.55 + 0.55 * Math.cos(a), bt - 0.55 + 0.55 * Math.sin(a))); }
bp.push(new THREE.Vector2(Rbtn - 1.2, bt), new THREE.Vector2(Rbtn - 1.4, bt - 0.15), new THREE.Vector2(0.001, bt - 0.15));
const button = new THREE.Mesh(new THREE.LatheGeometry(bp, 160), new THREE.MeshPhysicalMaterial({ color: '#A5ABB3', roughness: 0.55, clearcoat: 0.12, clearcoatRoughness: 0.5, envMapIntensity: 0.7 }));
button.castShadow = true; vial.add(button);


// label: real print file on the straight body, same rotation for every product
const LABEL_H = 16.5, LABEL_W = LABEL_H * (labelTex.image.width / labelTex.image.height), rL = Rb + 0.05;
const thetaLength = LABEL_W / rL;

const label = new THREE.Mesh(new THREE.CylinderGeometry(rL, rL, LABEL_H, 256, 1, true, -U_CENTER * thetaLength, thetaLength),
  new THREE.MeshPhysicalMaterial({ map: labelTex, roughness: 0.58, clearcoat: 0.16, clearcoatRoughness: 0.3, envMapIntensity: 0.35, side: THREE.FrontSide,
    transparent: true, opacity: 1, depthWrite: true }));   // transparent = excluded from the glass's refraction texture
label.position.y = 14; label.castShadow = true; vial.add(label);
const backing = new THREE.Mesh(new THREE.CylinderGeometry(rL - 0.02, rL - 0.02, LABEL_H, 256, 1, true, -U_CENTER * thetaLength, thetaLength),
  new THREE.MeshStandardMaterial({ color: '#F4F2EC', roughness: 0.9, side: THREE.BackSide }));
backing.position.y = label.position.y; vial.add(backing);


vial.children.forEach(part => { part.position.y -= bt / 2; });
return vial;
}

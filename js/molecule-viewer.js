(function () {
  const COLORS = {
    hydrogen: 0xffffff,
    carbon: 0x30343b,
    oxygen: 0xd4472f,
    nitrogen: 0x2f62d0,
    sulfur: 0xf0c040,
    chlorine: 0x31a354,
    sodium: 0x7b61ff,
    fluorine: 0x44cc88,
    bromine: 0x8b3a1f,
  };
  const RADII = {
    hydrogen: 0.25,
    carbon: 0.42,
    oxygen: 0.43,
    nitrogen: 0.42,
    sulfur: 0.5,
    chlorine: 0.5,
    sodium: 0.52,
    fluorine: 0.4,
    bromine: 0.54,
  };

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  function disposeScene(state) {
    if (!state) return;
    state.disposed = true;
    window.removeEventListener("resize", state.resize);
    state.scene.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) obj.material.forEach((mat) => mat.dispose());
        else obj.material.dispose();
      }
    });
    state.renderer.dispose();
  }

  function render(canvas, visualizationData) {
    if (!canvas || !window.THREE) return null;
    if (canvas.__chemvisionViewer) disposeScene(canvas.__chemvisionViewer);

    const THREE = window.THREE;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
    camera.position.set(0, 0, 12);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene.add(new THREE.AmbientLight(0xffffff, 0.62));
    const key = new THREE.DirectionalLight(0xffffff, 1);
    key.position.set(-4, 6, 7);
    scene.add(key);
    const root = new THREE.Group();
    scene.add(root);

    const mols = visualizationData && visualizationData.molecules;
    const molecules = [...list(mols && mols.reactants), ...list(mols && mols.products)];
    const sphereGeo = new THREE.SphereGeometry(1, 32, 32);
    const bondGeo = new THREE.CylinderGeometry(1, 1, 1, 18, 1, true);
    const up = new THREE.Vector3(0, 1, 0);

    molecules.forEach((mol, molIdx) => {
      const group = new THREE.Group();
      const atomPositions = new Map();
      list(mol.atoms).forEach((atom) => {
        const element = atom.element || "carbon";
        const mesh = new THREE.Mesh(
          sphereGeo,
          new THREE.MeshPhongMaterial({ color: COLORS[element] || 0x8fb3b6, shininess: 80 })
        );
        mesh.scale.setScalar(RADII[element] || 0.4);
        mesh.position.fromArray(atom.position || [0, 0, 0]);
        atomPositions.set(atom.id, mesh.position.clone());
        group.add(mesh);
      });
      list(mol.bonds).forEach((bond) => {
        const a = atomPositions.get(bond.from);
        const b = atomPositions.get(bond.to);
        if (!a || !b) return;
        const dir = new THREE.Vector3().subVectors(b, a);
        const len = dir.length();
        if (len < 0.001) return;
        const cyl = new THREE.Mesh(
          bondGeo,
          new THREE.MeshPhongMaterial({ color: 0xa9b7b8, shininess: 25 })
        );
        const order = Math.max(1, bond.order || 1);
        cyl.scale.set(0.055 * order, len, 0.055 * order);
        cyl.position.copy(a).addScaledVector(dir, 0.5);
        cyl.quaternion.setFromUnitVectors(up, dir.clone().normalize());
        group.add(cyl);
      });
      group.position.x = (molIdx - (molecules.length - 1) / 2) * 3.2;
      root.add(group);
    });

    let rx = 0.25;
    let ry = 0.55;
    let dragging = false;
    let lx = 0;
    let ly = 0;
    let zoom = 12;
    canvas.onpointerdown = (event) => {
      dragging = true;
      lx = event.clientX;
      ly = event.clientY;
      canvas.setPointerCapture(event.pointerId);
    };
    canvas.onpointermove = (event) => {
      if (!dragging) return;
      ry += (event.clientX - lx) * 0.006;
      rx += (event.clientY - ly) * 0.005;
      lx = event.clientX;
      ly = event.clientY;
    };
    canvas.onpointerup = () => (dragging = false);
    canvas.onpointerleave = () => (dragging = false);
    canvas.onwheel = (event) => {
      event.preventDefault();
      zoom = Math.max(5, Math.min(32, zoom + event.deltaY * 0.01));
    };

    const state = {
      disposed: false,
      scene,
      renderer,
      resize() {
        const w = canvas.clientWidth || 1;
        const h = canvas.clientHeight || 1;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      },
    };
    canvas.__chemvisionViewer = state;
    window.addEventListener("resize", state.resize);
    state.resize();

    function loop() {
      if (state.disposed) return;
      requestAnimationFrame(loop);
      root.rotation.x += (rx - root.rotation.x) * 0.08;
      root.rotation.y += (ry - root.rotation.y) * 0.08;
      camera.position.z += (zoom - camera.position.z) * 0.12;
      renderer.render(scene, camera);
    }
    loop();
    return state;
  }

  window.ChemVisionMoleculeViewer = { render, disposeScene };
})();

(function () {
  const api = window.ChemVisionAPI;
  if (!api || !api.requireAuth()) return;

  const $ = (id) => document.getElementById(id);

  // ── element colours (CPK) ─────────────────────────────────────────────────
  const ELEMENT = {
    hydrogen: { symbol: "H", color: 0xf5f7f8, radius: 0.30 },
    carbon:   { symbol: "C", color: 0x343a40, radius: 0.46 },
    oxygen:   { symbol: "O", color: 0xe3423b, radius: 0.48 },
    nitrogen: { symbol: "N", color: 0x3568d4, radius: 0.46 },
    chlorine: { symbol: "Cl", color: 0x3aab57, radius: 0.52 },
    sodium:   { symbol: "Na", color: 0x8c75e8, radius: 0.52 },
    sulfur:   { symbol: "S", color: 0xe8c43b, radius: 0.50 },
    fluorine: { symbol: "F", color: 0x51bd82, radius: 0.44 },
    bromine:  { symbol: "Br", color: 0xaa492f, radius: 0.54 },
    phosphorus:{ symbol: "P", color: 0xe88137, radius: 0.50 },
  };

  // ── state ─────────────────────────────────────────────────────────────────
  let currentMolData = null;
  let searchTimer    = null;
  let threeState     = null;   // { renderer, scene, camera, root, … }
  let atomLabels     = [];

  // ── identity ──────────────────────────────────────────────────────────────
  async function loadIdentity() {
    try {
      const user = await api.profile();
      api.saveSession({ user });
      $("topName").textContent   = user.full_name;
      $("topField").textContent  = user.field_of_study || "Chemistry";
      $("topAvatar").textContent = api.initials(user.full_name);
    } catch (_) {}
  }

  // ── toast ─────────────────────────────────────────────────────────────────
  let toastTimer;
  function showToast(msg) {
    $("toastText").textContent = msg;
    const t = $("toast");
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
  }

  // ── search ────────────────────────────────────────────────────────────────
  $("molSearch").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    if (!e.target.value.trim()) {
      $("searchResults").innerHTML = "";
      return;
    }
    searchTimer = setTimeout(() => doSearch(e.target.value.trim()), 450);
  });

  $("molSearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      clearTimeout(searchTimer);
      doSearch($("molSearch").value.trim());
    }
  });

  $("searchBtn").addEventListener("click", () => {
    clearTimeout(searchTimer);
    doSearch($("molSearch").value.trim());
  });

  async function doSearch(q) {
    if (!q) return;
    $("searchBtn").disabled = true;
    $("searchResults").innerHTML = `<div class="search-loading">Searching…</div>`;
    try {
      const results = await api.searchMolecules(q);
      renderSearchResults(results);
    } catch (err) {
      $("searchResults").innerHTML =
        `<div class="search-error">${api.escapeHtml(err.message)}</div>`;
    } finally {
      $("searchBtn").disabled = false;
    }
  }

  function renderSearchResults(results) {
    if (!results || results.length === 0) {
      $("searchResults").innerHTML =
        `<div class="search-error">No molecules found. Try a different name or SMILES.</div>`;
      return;
    }
    $("searchResults").innerHTML = results
      .map(
        (r, i) => `
        <div class="search-result-item" data-idx="${i}">
          <div class="result-name">${api.escapeHtml(r.name || r.smiles)}</div>
          <div class="result-meta">${api.escapeHtml(r.formula || "")}${r.molecular_weight ? " · " + parseFloat(r.molecular_weight).toFixed(2) + " g/mol" : ""} · ${api.escapeHtml(r.source || "")}</div>
        </div>`
      )
      .join("");

    $("searchResults").querySelectorAll(".search-result-item").forEach((el) => {
      el.addEventListener("click", () => {
        const r = results[parseInt(el.dataset.idx)];
        loadMolecule(r);
        $("searchResults").innerHTML = "";
      });
    });
  }

  // ── validate SMILES directly ──────────────────────────────────────────────
  async function validateAndLoad(smiles, name) {
    try {
      const mol = await api.validateMolecule({ query: smiles, name: name || null });
      loadMolecule({ ...mol, source: "RDKit" });
    } catch (err) {
      showToast("Invalid SMILES: " + err.message);
    }
  }

  // ── load molecule into panel + 3D ─────────────────────────────────────────
  function loadMolecule(data) {
    currentMolData = data;

    // fill info panel
    $("molName").textContent   = data.name    || data.smiles || "Molecule";
    $("molFormula").textContent = data.formula || "—";
    $("molMW").textContent     = data.molecular_weight
      ? parseFloat(data.molecular_weight).toFixed(3) + " g/mol"
      : "—";

    const vizData  = data.visualization_data || {};
    const allAtoms = [
      ...((vizData.molecules?.reactants || []).flatMap((m) => m.atoms || [])),
      ...((vizData.molecules?.products  || []).flatMap((m) => m.atoms || [])),
    ];
    const allBonds = [
      ...((vizData.molecules?.reactants || []).flatMap((m) => m.bonds || [])),
      ...((vizData.molecules?.products  || []).flatMap((m) => m.bonds || [])),
    ];

    // For a single molecule, atoms/bonds may be directly on the object
    const atoms = data.atoms || allAtoms;
    const bonds = data.bonds || allBonds;

    $("molAtoms").textContent  = atoms.length || "—";
    $("molBonds").textContent  = bonds.length || "—";
    $("molSource").textContent = data.source || "Search";
    $("molSmiles").textContent = data.smiles || "—";

    $("molInfo").classList.remove("hidden");
    $("molLegend").style.display = "flex";
    $("vpEmpty").style.display   = "none";

    // render 3D
    renderScene({ atoms, bonds });
  }

  // ── Three.js scene ────────────────────────────────────────────────────────
  function list(v) { return Array.isArray(v) ? v.filter(Boolean) : []; }

  function renderScene({ atoms, bonds }) {
    if (threeState) {
      threeState.dispose();
      threeState = null;
    }
    if (!list(atoms).length) {
      const canvas = $("molCanvas");
      if (canvas) canvas.style.display = "none";
      $("vpEmpty").style.display = "flex";
      $("vpEmpty").querySelector("p").textContent = "No 3D data available";
      $("vpEmpty").querySelector("span").textContent = "Choose a molecule with a supported 3D structure to view it here.";
      return;
    }
    if (!window.THREE) {
      $("vpEmpty").style.display = "flex";
      $("vpEmpty").querySelector("p").textContent = "Three.js not loaded";
      return;
    }
    const THREE = window.THREE;
    const canvasWrap = $("canvasWrap");

    // Replace canvas
    const oldCanvas = $("molCanvas");
    const canvas    = oldCanvas.cloneNode(false);
    canvas.style.display = "block";
    oldCanvas.replaceWith(canvas);

    const scene    = new THREE.Scene();
    const w        = canvasWrap.clientWidth  || 600;
    const h        = canvasWrap.clientHeight || 500;
    const camera   = new THREE.PerspectiveCamera(35, w / h, 0.1, 200);

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    } catch (_error) {
      $("vpEmpty").style.display = "flex";
      $("vpEmpty").querySelector("p").textContent = "3D graphics are unavailable";
      $("vpEmpty").querySelector("span").textContent = "This browser could not create a WebGL canvas.";
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h, false);

    // lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(-4, 6, 8);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x5ff0c4, 0.4);
    rim.position.set(6, -3, -6);
    scene.add(rim);

    const root = new THREE.Group();
    scene.add(root);

    // build atoms
    const byId     = new Map();
    const radiiById = new Map();
    atomLabels = [];
    const sphereGeo = new THREE.SphereGeometry(1, 48, 36);
    list(atoms).forEach((atom) => {
      const meta = ELEMENT[atom.element] || { symbol: atom.element || "?", color: 0x8fb3b6, radius: 0.42 };
      const mesh = new THREE.Mesh(
        sphereGeo,
        new THREE.MeshPhongMaterial({
          color: meta.color,
          specular: 0xffffff,
          shininess: 115,
          emissive: meta.color,
          emissiveIntensity: 0.035,
        })
      );
      mesh.scale.setScalar(meta.radius);
      mesh.position.fromArray(atom.position || [0, 0, 0]);
      byId.set(atom.id, mesh.position.clone());
      radiiById.set(atom.id, meta.radius);
      root.add(mesh);

      const labelCanvas = document.createElement("canvas");
      labelCanvas.width = 128;
      labelCanvas.height = 88;
      const ctx = labelCanvas.getContext("2d");
        if (!ctx) return;
      ctx.fillStyle = "rgba(17, 20, 22, .68)";
      ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(12, 10, 104, 68, 15);
        else ctx.rect(12, 10, 104, 68);
      ctx.fill();
      ctx.fillStyle = "rgba(238, 244, 246, .9)";
      ctx.font = "600 44px Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(meta.symbol || "?", 64, 45);
      const texture = new THREE.CanvasTexture(labelCanvas);
      if (THREE.SRGBColorSpace) texture.colorSpace = THREE.SRGBColorSpace;
      const label = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false }));
      label.scale.set(meta.symbol.length > 1 ? 0.62 : 0.48, 0.34, 1);
      label.position.copy(mesh.position).add(new THREE.Vector3(0, meta.radius + 0.20, 0));
      label.renderOrder = 10;
      root.add(label);
      atomLabels.push(label);
    });

    // build bonds
    const bondGeo = new THREE.CylinderGeometry(1, 1, 1, 14, 1, true);
    const bondMat = new THREE.MeshPhongMaterial({ color: 0xb6c0c5, specular: 0xffffff, shininess: 100 });
    const up      = new THREE.Vector3(0, 1, 0);
    list(bonds).forEach((bond) => {
      const a = byId.get(bond.from);
      const b = byId.get(bond.to);
      if (!a || !b) return;
      const dir = new THREE.Vector3().subVectors(b, a);
      if (dir.length() < 0.001) return;
      dir.normalize();
      const start = a.clone().addScaledVector(dir, (radiiById.get(bond.from) || 0.4) * 0.74);
      const end = b.clone().addScaledVector(dir, -(radiiById.get(bond.to) || 0.4) * 0.74);
      const bondVector = new THREE.Vector3().subVectors(end, start);
      const length = bondVector.length();
      if (length < 0.05) return;
      let perpendicular = new THREE.Vector3().crossVectors(dir, up).normalize();
      if (perpendicular.lengthSq() < 0.001) perpendicular.set(1, 0, 0);
      const order = Number(bond.order) || 1;
      const count = order >= 2.5 ? 3 : order >= 1.5 ? 2 : 1;
      const spacing = count === 3 ? 0.135 : 0.105;
      const offsets = count === 1 ? [0] : count === 2 ? [-spacing / 2, spacing / 2] : [-spacing, 0, spacing];
      offsets.forEach((offset) => {
        const cyl = new THREE.Mesh(bondGeo, bondMat);
        const radius = count === 1 ? 0.075 : 0.052;
        cyl.scale.set(radius, length, radius);
        cyl.position.copy(start).add(end).multiplyScalar(0.5).addScaledVector(perpendicular, offset);
        cyl.quaternion.setFromUnitVectors(up, bondVector.clone().normalize());
        root.add(cyl);
      });
    });

    const bounds = new THREE.Box3().setFromObject(root);
    const center = bounds.getCenter(new THREE.Vector3());
    root.position.sub(center);
    const sphere = bounds.getBoundingSphere(new THREE.Sphere());
    const fitDistance = Math.max(6, sphere.radius / Math.sin(THREE.MathUtils.degToRad(35 / 2)) * 1.12);
    const minZoom = Math.max(4, fitDistance * 0.48);
    const maxZoom = Math.max(36, fitDistance * 2.4, bounds.getSize(new THREE.Vector3()).length() * 2.5);
    camera.position.set(0, 0, fitDistance);
    camera.far = maxZoom * 5;
    camera.updateProjectionMatrix();

    // interaction
    let tx = 0.1, ty = 0.4, cx = 0.1, cy = 0.4;
    let dragging = false, lx = 0, ly = 0, zoom = fitDistance;

    canvas.addEventListener("pointerdown", (e) => {
      dragging = true; lx = e.clientX; ly = e.clientY;
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      ty += (e.clientX - lx) * 0.006;
      tx  = Math.max(-1.2, Math.min(1.2, tx + (e.clientY - ly) * 0.005));
      lx = e.clientX; ly = e.clientY;
    });
    ["pointerup", "pointercancel"].forEach((n) =>
      canvas.addEventListener(n, () => (dragging = false))
    );
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      zoom = Math.max(minZoom, Math.min(maxZoom, zoom + e.deltaY * 0.015));
    }, { passive: false });

    // toolbar
    $("vpReset").onclick = () => { tx = 0.1; ty = 0.4; zoom = fitDistance; };
    $("vpFit").onclick   = () => { zoom = fitDistance; };
    const labelsBtn = $("vpLabels");
    if (labelsBtn) labelsBtn.onclick = () => {
      const visible = labelsBtn.getAttribute("aria-pressed") !== "true";
      labelsBtn.setAttribute("aria-pressed", String(visible));
      labelsBtn.textContent = visible ? "Labels on" : "Labels off";
      atomLabels.forEach((label) => { label.visible = visible; });
    };
    $("vpFull").onclick  = () =>
      !document.fullscreenElement
        ? canvasWrap.requestFullscreen?.()
        : document.exitFullscreen?.();

    function resize() {
      const nw = canvasWrap.clientWidth;
      const nh = canvasWrap.clientHeight;
      if (!nw || !nh) return;
      renderer.setSize(nw, nh, false);
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize);
    document.addEventListener("fullscreenchange", () => setTimeout(resize, 50));
    resize();

    let rafId;
    function loop() {
      rafId = requestAnimationFrame(loop);
      cx += (tx - cx) * 0.08;
      cy += (ty - cy) * 0.08;
      camera.position.z += (zoom - camera.position.z) * 0.12;
      root.rotation.set(cx, cy, 0);
      renderer.render(scene, camera);
    }
    loop();

    threeState = {
      dispose() {
        cancelAnimationFrame(rafId);
        window.removeEventListener("resize", resize);
        renderer.dispose();
        scene.traverse((obj) => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) {
            const materials = Array.isArray(obj.material) ? obj.material : [obj.material];
            materials.forEach((material) => {
              if (material.map) material.map.dispose();
              material.dispose();
            });
          }
        });
      },
    };
  }

  // ── save molecule ─────────────────────────────────────────────────────────
  $("saveBtn").addEventListener("click", async () => {
    if (!currentMolData || !currentMolData.smiles) return;
    $("saveBtn").disabled    = true;
    $("saveBtn").textContent = "Saving…";
    try {
      await api.saveMolecule({
        name:        currentMolData.name || currentMolData.smiles,
        smiles:      currentMolData.smiles,
        source:      currentMolData.source || "Studio",
        identifiers: currentMolData.identifiers || {},
      });
      showToast("Molecule saved to your collection");
      loadSaved();
    } catch (err) {
      showToast("Save failed: " + err.message);
    } finally {
      $("saveBtn").disabled    = false;
      $("saveBtn").textContent = "Save Molecule";
    }
  });

  // ── copy SMILES ───────────────────────────────────────────────────────────
  $("copyBtn").addEventListener("click", () => {
    if (!currentMolData?.smiles) return;
    navigator.clipboard?.writeText(currentMolData.smiles).then(() => {
      showToast("SMILES copied to clipboard");
    }).catch(() => {
      showToast("SMILES: " + currentMolData.smiles);
    });
  });

  // ── load saved molecules ──────────────────────────────────────────────────
  async function loadSaved() {
    const list = $("savedList");
    try {
      const saved = await api.savedMolecules();
      if (!saved.length) {
        list.innerHTML = `<p style="font-size:13px;color:var(--muted);padding:8px 4px">No saved molecules yet.</p>`;
        return;
      }
      list.innerHTML = saved
        .map(
          (m) => `
          <div class="saved-item" data-smiles="${api.escapeHtml(m.smiles)}" data-name="${api.escapeHtml(m.name)}">
            <span class="saved-dot"></span>
            <div class="saved-item-text">
              <div class="saved-item-name">${api.escapeHtml(m.name)}</div>
              <div class="saved-item-meta">${api.escapeHtml(m.formula || m.smiles)}</div>
            </div>
          </div>`
        )
        .join("");
      list.querySelectorAll(".saved-item").forEach((el) => {
        el.addEventListener("click", () =>
          validateAndLoad(el.dataset.smiles, el.dataset.name)
        );
      });
    } catch (_) {
      list.innerHTML = `<p style="font-size:13px;color:var(--muted);padding:8px 4px">Could not load saved molecules.</p>`;
    }
  }

  // ── exit ──────────────────────────────────────────────────────────────────
  document.querySelectorAll(".exit").forEach((el) => {
    el.addEventListener("click", (e) => { e.preventDefault(); api.logout(); });
  });

  // ── init ──────────────────────────────────────────────────────────────────
  loadIdentity();
  loadSaved();
})();

/**
 * ChemVision AI — Visualizer page controller
 *
 * Loads a reaction from the backend API (by ?id= param or most recent),
 * populates every panel with real data, renders 3-D ball-and-stick molecules,
 * and drives the play/pause/step animation.
 */
(function () {
  const api = window.ChemVisionAPI;
  if (!api || !api.requireAuth()) return;

  const $ = (id) => document.getElementById(id);

  // ── element appearance ────────────────────────────────────────────────────
  const ELEMENT = {
    hydrogen: { label: "Hydrogen", symbol: "H", color: 0xf5f7f8, radius: 0.30 },
    carbon:   { label: "Carbon", symbol: "C", color: 0x343a40, radius: 0.46 },
    oxygen:   { label: "Oxygen", symbol: "O", color: 0xe3423b, radius: 0.48 },
    nitrogen: { label: "Nitrogen", symbol: "N", color: 0x3568d4, radius: 0.46 },
    chlorine: { label: "Chlorine", symbol: "Cl", color: 0x3aab57, radius: 0.52 },
    sodium:   { label: "Sodium", symbol: "Na", color: 0x8c75e8, radius: 0.52 },
    sulfur:   { label: "Sulfur", symbol: "S", color: 0xe8c43b, radius: 0.50 },
    fluorine: { label: "Fluorine", symbol: "F", color: 0x51bd82, radius: 0.44 },
    bromine:  { label: "Bromine", symbol: "Br", color: 0xaa492f, radius: 0.54 },
    phosphorus:{ label: "Phosphorus", symbol: "P", color: 0xe88137, radius: 0.50 },
  };

  // ── utilities ─────────────────────────────────────────────────────────────
  function list(v) { return Array.isArray(v) ? v.filter(Boolean) : []; }

  function formatMw(mw) {
    if (!mw || mw === 0) return "—";
    return parseFloat(mw).toFixed(2) + " g/mol";
  }

  // ── build page-data from the API reaction object ──────────────────────────
  /**
   * Converts the backend ReactionRead object into the shape expected by
   * window.renderReaction() (defined in visualizer.html's inline <script>).
   *
   * The backend stores:
   *   reaction.reactants   = ["Methane", "Oxygen"]   (string names)
   *   reaction.products    = ["Carbon Dioxide", "Water"]
   *   reaction.visualization_data.molecules.reactants = [{name, formula, molecular_weight, atoms, bonds, coefficient, smiles}, ...]
   *   reaction.visualization_data.molecules.products  = [...]
   */
  function reactionToPageData(reaction) {
    const vizData   = reaction.visualization_data || { molecules: { reactants: [], products: [] } };
    const vizMols   = vizData.molecules || {};
    const rMols     = list(vizMols.reactants);
    const pMols     = list(vizMols.products);

    // Prefer rich molecule objects; fall back to plain name strings
    const compounds = [
      ...rMols.map((m) => ({
        name:    m.name    || "Unknown",
        formula: m.formula || "—",
        weight:  formatMw(m.molecular_weight),
        coeff:   m.coefficient != null ? m.coefficient : 1,
        role:    "Reactant",
      })),
      ...pMols.map((m) => ({
        name:    m.name    || "Unknown",
        formula: m.formula || "—",
        weight:  formatMw(m.molecular_weight),
        coeff:   m.coefficient != null ? m.coefficient : 1,
        role:    "Product",
      })),
    ];

    // Fallback: if visualization_data has no molecules, use plain name arrays
    if (!compounds.length) {
      const rNames = list(reaction.reactants);
      const pNames = list(reaction.products);
      rNames.forEach((n) => compounds.push({ name: n, formula: n, weight: "—", coeff: 1, role: "Reactant" }));
      pNames.forEach((n) => compounds.push({ name: n, formula: n, weight: "—", coeff: 1, role: "Product" }));
    }

    const reactantNames = rMols.length
      ? rMols.map((m) => (m.coefficient > 1 ? `${m.coefficient} ${m.name}` : m.name))
      : list(reaction.reactants);
    const productNames  = pMols.length
      ? pMols.map((m) => (m.coefficient > 1 ? `${m.coefficient} ${m.name}` : m.name))
      : list(reaction.products);

    const tags = list(reaction.conditions).concat(reaction.catalyst ? [reaction.catalyst] : []);

    const steps = reactantNames.length
      ? [
          {
            title: "Reactants present",
            text:  reactantNames.join(" + ") + " are the starting materials.",
          },
          {
            title: "Reaction begins",
            text:  reaction.summary || "Bonds begin to break and reform.",
          },
          {
            title: "Conditions",
            text:  list(reaction.conditions).join(", ") || "See reaction details.",
          },
          {
            title: "Products form",
            text:  productNames.length
              ? productNames.join(" + ") + " are produced."
              : "Products are determined by the reaction pathway.",
          },
          {
            title: "Safety review",
            text:  reaction.safety_notes || "Confirm chemistry before laboratory use.",
          },
        ]
      : [
          { title: "Reaction uploaded",  text: "The image has been saved for review." },
          { title: "Identification",     text: reaction.summary || "Reaction could not be confidently identified." },
          { title: "Action required",    text: "Upload a clearer image or rename the file to match a known reaction." },
          { title: "Example filename",   text: "Try: methane_combustion.png or hcl_naoh.png" },
          { title: "Supported list",     text: "Methane combustion, Hydrogen combustion, HCl+NaOH, Fischer esterification, Water electrolysis." },
        ];

    return {
      title:       reaction.reaction_name  || "Uploaded Reaction",
      equationHTML: api.formatEquation(reaction.equation),
      chip:        (reaction.reaction_type || "Reaction") +
                   (reaction.requires_verification ? " · NEEDS REVIEW" : ""),
      summary:     reaction.summary   || "No summary available.",
      mechanism:   reaction.mechanism || "No mechanism available until the reaction is verified.",
      tags,
      stats: [
        { k: "Reaction class", v: reaction.reaction_type || "Unknown",        sm: true },
        { k: "Catalyst",       v: reaction.catalyst      || "None listed",    sm: true },
        { k: "Temperature",    v: reaction.temperature   || "Not specified",  sm: true },
        {
          k: "OCR confidence",
          v: reaction.ocr_confidence == null
            ? "—"
            : Math.round(reaction.ocr_confidence * 100) + "%",
        },
      ],
      details: [
        { k: "Reaction type", v: reaction.reaction_type || "Unknown" },
        { k: "Conditions",    v: list(reaction.conditions).join(", ") || "Not specified" },
        { k: "Catalyst",      v: reaction.catalyst      || "None listed" },
        { k: "Temperature",   v: reaction.temperature   || "Not specified" },
        { k: "Verification",  v: reaction.requires_verification ? "Needs review" : "Matched to known reaction" },
        { k: "Extracted text", v: reaction.extracted_text || "No OCR text captured" },
      ],
      compounds,
      atoms:  atomRows(vizData),
      safety: {
        title: "Handling note",
        text:  reaction.safety_notes || "Use standard laboratory safety practices.",
      },
      steps,
    };
  }

  // ── atom summary table rows ───────────────────────────────────────────────
  function atomRows(visualizationData) {
    const counts = {};
    const groups = visualizationData && visualizationData.molecules;
    [
      ...list(groups && groups.reactants),
      ...list(groups && groups.products),
    ].forEach((mol) => {
      list(mol.atoms).forEach((atom) => {
        const key = atom.element || "unknown";
        counts[key] = (counts[key] || 0) + 1;
      });
    });
    return Object.entries(counts).map(([element, count]) => ({
      el:    ELEMENT[element] ? ELEMENT[element].label : element,
      count,
      role:  "Model atom",
      cls:   element === "carbon" ? "c" : element === "oxygen" ? "o" : "h",
    }));
  }

  // ── topbar identity ───────────────────────────────────────────────────────
  function setIdentity(user) {
    if (!user) return;
    const name   = document.querySelector(".identity .who b");
    const field  = document.querySelector(".identity .who span");
    const avatar = document.querySelector(".avatar");
    if (name)   name.textContent   = user.full_name;
    if (field)  field.textContent  = user.field_of_study || "Chemistry";
    if (avatar) avatar.textContent = api.initials(user.full_name);
  }

  // ── main load ─────────────────────────────────────────────────────────────
  async function loadReaction() {
    try {
      const user = await api.profile();
      setIdentity(user);

      const params = new URLSearchParams(window.location.search);
      let id = params.get("id");
      if (!id) {
        const reactions = await api.reactions();
        id = reactions[0] && reactions[0].id;
      }
      if (!id) throw new Error("Upload a reaction from the dashboard first.");

      const reaction = await api.reaction(id);

      // Populate all text panels via the existing renderReaction() in the page
      window.renderReaction(reactionToPageData(reaction));

      // Update the live/verified badge
      const liveTag = $("liveTag");
      if (liveTag) {
        liveTag.className = "live on";
        liveTag.innerHTML = `<i></i>${reaction.requires_verification ? "Needs review" : "Backend data"}`;
      }

      // Render 3-D scene from API visualization data
      renderMoleculeScene(reaction.visualization_data, reaction.image_path);

    } catch (error) {
      const summary = $("infoSummary");
      if (summary) summary.textContent = error.message;
      // Still show a usable page with the error in the topbar equation
      const eqnTop = $("rxnEqnTop");
      if (eqnTop) eqnTop.textContent = error.message;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 3-D molecule scene (Three.js)
  // ─────────────────────────────────────────────────────────────────────────

  // Module-level animation state so play/pause can reach it
  let _animState = null;
  let labelSprites = [];
  let activeSourcePreviewUrl = null;

  function showViewerEmpty(imagePath, title, message) {
    const canvas = $("mol");
    const panel = $("viewerEmpty");
    const image = $("sourcePreview");
    const modePill = document.querySelector(".mode-pill");
    if (canvas) canvas.style.display = "none";
    if (panel) panel.hidden = false;
    if (modePill) modePill.textContent = "SOURCE IMAGE";
    if ($("viewerEmptyTitle")) $("viewerEmptyTitle").textContent = title;
    if ($("viewerEmptyText")) $("viewerEmptyText").textContent = message;
    if (!image) return;
    if (imagePath) {
      image.hidden = false;
      image.alt = "Uploaded reaction image for review";
      fetch(new URL(imagePath, api.API_BASE || window.location.origin).href, {
        headers: { Authorization: `Bearer ${api.token()}` },
      }).then((response) => {
        if (!response.ok) throw new Error("Image unavailable");
        return response.blob();
      }).then((blob) => {
        if (!image.isConnected) return;
        if (activeSourcePreviewUrl) URL.revokeObjectURL(activeSourcePreviewUrl);
        activeSourcePreviewUrl = URL.createObjectURL(blob);
        image.src = activeSourcePreviewUrl;
      }).catch(() => {
        image.hidden = true;
        image.removeAttribute("src");
      });
    } else {
      image.removeAttribute("src");
      image.hidden = true;
    }
  }

  function renderMoleculeScene(visualizationData, imagePath) {
    const oldCanvas = $("mol");
    if (!oldCanvas) return;
    if (!window.THREE) {
      showViewerEmpty(imagePath, "3D renderer could not load", "Your uploaded image is shown for review. Check the connection to the Three.js library and reload to try the 3D view again.");
      return;
    }

    const data = visualizationData || { molecules: { reactants: [], products: [] } };
    const reactants = list(data.molecules && data.molecules.reactants);
    const products = list(data.molecules && data.molecules.products);
    const allMolecules = [...reactants, ...products];
    // The backend marks a reaction unavailable when RDKit could not build
    // every molecule. Showing only the subset would misrepresent the reaction.
    const hasIncompleteModel = data.engine === "unavailable";
    const hasCompleteModel = allMolecules.length > 0 && allMolecules.every((mol) =>
      list(mol.atoms).length > 0 && list(mol.bonds).length > 0
    );
    if (hasIncompleteModel || !hasCompleteModel) {
      showViewerEmpty(
        imagePath,
        "No verified 3D structure is available",
        "The uploaded image is preserved for review. ChemVision draws the 3D reaction only when it can build every molecule; it will not show a partial or guessed reaction."
      );
      return;
    }

    // Replace canvas to reset any existing WebGL context
    const canvas = oldCanvas.cloneNode(false);
    oldCanvas.replaceWith(canvas);
    canvas.style.display = "block";
    const modePill = document.querySelector(".mode-pill");
    if (modePill) modePill.textContent = "BALL & STICK";
    const emptyPanel = $("viewerEmpty");
    if (emptyPanel) emptyPanel.hidden = true;
    labelSprites = [];

    const THREE  = window.THREE;
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 200);
    camera.position.set(0, 0, 18);

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    } catch (_error) {
      showViewerEmpty(imagePath, "3D graphics are unavailable", "Your uploaded image is shown for review. This browser could not create a WebGL canvas for the molecular model.");
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.58));
    const key = new THREE.DirectionalLight(0xffffff, 0.95);
    key.position.set(-4, 6, 8);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x5ff0c4, 0.45);
    rim.position.set(6, -3, -6);
    scene.add(rim);

    // Root group that we rotate
    const root = new THREE.Group();
    scene.add(root);

    // ── build molecule meshes ──────────────────────────────────────────────
    function buildMolecule(molData) {
      const group    = new THREE.Group();
      const atoms    = list(molData.atoms);
      const byId     = new Map();
      const radiiById = new Map();
      const sphereGeo = new THREE.SphereGeometry(1, 48, 36);

      atoms.forEach((atom) => {
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
        group.add(mesh);

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
        const labelTexture = new THREE.CanvasTexture(labelCanvas);
        if (THREE.SRGBColorSpace) labelTexture.colorSpace = THREE.SRGBColorSpace;
        const label = new THREE.Sprite(new THREE.SpriteMaterial({
          map: labelTexture,
          transparent: true,
          depthTest: false,
          sizeAttenuation: true,
        }));
        label.scale.set(meta.symbol.length > 1 ? 0.62 : 0.48, 0.34, 1);
        label.position.copy(mesh.position).add(new THREE.Vector3(0, meta.radius + 0.20, 0));
        label.renderOrder = 10;
        group.add(label);
        labelSprites.push(label);
      });

      const bondGeo = new THREE.CylinderGeometry(1, 1, 1, 16, 1, true);
      const bondMat = new THREE.MeshPhongMaterial({ color: 0xb6c0c5, specular: 0xffffff, shininess: 100 });
      const up      = new THREE.Vector3(0, 1, 0);
      list(molData.bonds).forEach((bond) => {
        const a = byId.get(bond.from);
        const b = byId.get(bond.to);
        if (!a || !b) return;
        const dir = new THREE.Vector3().subVectors(b, a);
        if (dir.length() < 0.001) return;
        dir.normalize();
        const start = a.clone().addScaledVector(dir, (radiiById.get(bond.from) || 0.4) * 0.74);
        const end = b.clone().addScaledVector(dir, -(radiiById.get(bond.to) || 0.4) * 0.74);
        const bondVector = new THREE.Vector3().subVectors(end, start);
        const bondLength = bondVector.length();
        if (bondLength < 0.05) return;
        let perpendicular = new THREE.Vector3().crossVectors(dir, up).normalize();
        if (perpendicular.lengthSq() < 0.001) perpendicular.set(1, 0, 0);
        const order = Number(bond.order) || 1;
        const count = order >= 2.5 ? 3 : order >= 1.5 ? 2 : 1;
        const spacing = count === 3 ? 0.135 : 0.105;
        const offsets = count === 1 ? [0] : count === 2 ? [-spacing / 2, spacing / 2] : [-spacing, 0, spacing];
        offsets.forEach((offset) => {
          const cyl = new THREE.Mesh(bondGeo, bondMat);
          const radius = count === 1 ? 0.075 : 0.052;
          cyl.scale.set(radius, bondLength, radius);
          cyl.position.copy(start).add(end).multiplyScalar(0.5).addScaledVector(perpendicular, offset);
          cyl.quaternion.setFromUnitVectors(up, bondVector.clone().normalize());
          group.add(cyl);
        });
      });
      return group;
    }

    // ── place molecules left (reactants) and right (products) ─────────────
    const reactantGroups = [];
    const productGroups  = [];
    const SIDE_OFFSET    = 4.5;  // X separation between reactant/product sides

    reactants.forEach((mol, idx) => {
      const g      = buildMolecule(mol);
      const total  = reactants.length;
      const spread = Math.max(2.5, total * 2.2);
      g.position.x = -SIDE_OFFSET;
      g.position.y = (idx - (total - 1) / 2) * spread;
      root.add(g);
      reactantGroups.push(g);
    });

    products.forEach((mol, idx) => {
      const g      = buildMolecule(mol);
      const total  = products.length;
      const spread = Math.max(2.5, total * 2.2);
      g.position.x = SIDE_OFFSET;
      g.position.y = (idx - (total - 1) / 2) * spread;
      root.add(g);
      productGroups.push(g);
    });

    const bounds = new THREE.Box3().setFromObject(root);
    const center = bounds.getCenter(new THREE.Vector3());
    root.position.sub(center);
    const sphere = bounds.getBoundingSphere(new THREE.Sphere());
    const fitDistance = Math.max(8, sphere.radius / Math.sin(THREE.MathUtils.degToRad(35 / 2)) * 1.12);
    const minZoom = Math.max(5, fitDistance * 0.48);
    const maxZoom = Math.max(40, fitDistance * 2.4, bounds.getSize(new THREE.Vector3()).length() * 2.5);
    camera.position.z = fitDistance;
    camera.far = maxZoom * 5;
    camera.updateProjectionMatrix();

    if (!reactants.length && !products.length) {
      const note = $("whatText");
      if (note) {
        note.textContent =
          "3D visualization is unavailable for this reaction. " +
          "Chemical details are shown below.";
      }
    }

    // ── camera / interaction state ─────────────────────────────────────────
    let tx = 0.15, ty = 0.45;
    let cx = tx,   cy = ty;
    let dragging = false, lx = 0, ly = 0;
    let zoom = fitDistance;

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
    ["pointerup", "pointercancel", "pointerleave"].forEach((n) =>
      canvas.addEventListener(n, () => (dragging = false))
    );
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      zoom = Math.max(minZoom, Math.min(maxZoom, zoom + e.deltaY * 0.015));
    }, { passive: false });

    // ── toolbar buttons ────────────────────────────────────────────────────
    const btnReset = $("btnReset");
    const btnFit   = $("btnFit");
    const btnFull  = $("btnFull");
    const stageWrap = $("stageWrap");

    if (btnReset) btnReset.onclick = () => { tx = 0.15; ty = 0.45; zoom = fitDistance; };
    if (btnFit)   btnFit.onclick   = () => { zoom = fitDistance; };
    const btnLabels = $("btnLabels");
    if (btnLabels) {
      btnLabels.onclick = () => {
        const visible = btnLabels.getAttribute("aria-pressed") !== "true";
        btnLabels.setAttribute("aria-pressed", String(visible));
        btnLabels.textContent = visible ? "Labels on" : "Labels off";
        labelSprites.forEach((sprite) => { sprite.visible = visible; });
      };
    }
    if (btnFull && stageWrap) {
      btnFull.onclick = () =>
        !document.fullscreenElement
          ? stageWrap.requestFullscreen?.()
          : document.exitFullscreen?.();
    }

    // ── animation (play / pause / replay) ─────────────────────────────────
    /**
     * Three stages:
     *   0 = reactants visible at rest (products hidden)
     *   1 = reactants glide toward centre (products fade in)
     *   2 = products settle on right (reactants fade out)
     *
     * We track a continuous "animProgress" 0→1 per stage.
     */
    let animPlaying  = false;
    let animProgress = 0;   // 0..1 within current stage
    let animStage    = 0;   // 0,1,2

    // Show the complete reaction as the resting state. Playback begins at the
    // reactants when the user presses play.
    let initialFullReaction = true;

    function applyAnimStage(stage, progress) {
      const ease = (t) => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; // ease-in-out
      const p = Math.min(1, Math.max(0, ease(progress)));

      if (stage === 0) {
        // Resting — reactants at home, products hidden
        reactantGroups.forEach((g) => {
          g.position.x = -SIDE_OFFSET;
          g.visible = true;
        });
        productGroups.forEach((g) => { g.visible = false; });

      } else if (stage === 1) {
        // Reactants move toward centre
        reactantGroups.forEach((g) => {
          g.position.x = THREE.MathUtils.lerp(-SIDE_OFFSET, -SIDE_OFFSET * 0.3, p);
        });
        // Products start appearing from the right half-way through
        productGroups.forEach((g) => {
          g.visible = p > 0.4;
          if (p > 0.4) {
            const q = (p - 0.4) / 0.6;
            g.position.x = THREE.MathUtils.lerp(SIDE_OFFSET * 1.4, SIDE_OFFSET, q);
          }
        });

      } else if (stage === 2) {
        // Reactants fade back / products settle
        reactantGroups.forEach((g) => {
          g.position.x = THREE.MathUtils.lerp(-SIDE_OFFSET * 0.3, -SIDE_OFFSET, p);
          g.visible = p < 0.85;
        });
        productGroups.forEach((g) => {
          g.position.x = SIDE_OFFSET;
          g.visible = true;
        });
      }
    }

    // Expose animation state so play/pause button can reach it
    _animState = {
      play() {
        if (animPlaying) return;
        animPlaying = true;
        if (initialFullReaction) {
          initialFullReaction = false;
          animStage = 0;
          animProgress = 0;
          applyAnimStage(0, 0);
        }
        // If already at the end, replay from beginning
        if (animStage >= 2 && animProgress >= 1) {
          animStage    = 0;
          animProgress = 0;
          productGroups.forEach((g) => { g.visible = false; });
          reactantGroups.forEach((g) => {
            g.position.x = -SIDE_OFFSET;
            g.visible = true;
          });
        }
      },
      pause() { animPlaying = false; },
      replay() {
        animPlaying  = false;
        animStage    = 0;
        animProgress = 0;
        initialFullReaction = false;
        applyAnimStage(0, 0);
        reactantGroups.forEach((g) => {
          g.position.x = -SIDE_OFFSET;
          g.visible = true;
        });
        productGroups.forEach((g) => { g.visible = false; });
      },
      isPlaying() { return animPlaying; },
    };

    // ── resize ─────────────────────────────────────────────────────────────
    function resize() {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize);
    document.addEventListener("fullscreenchange", () => window.setTimeout(resize, 50));
    resize();

    // ── render loop ────────────────────────────────────────────────────────
    const ANIM_SPEED = 0.004; // progress units per frame (~60 fps)

    function loop() {
      requestAnimationFrame(loop);

      // Advance animation
      if (animPlaying) {
        animProgress += ANIM_SPEED;
        if (animProgress >= 1) {
          animProgress = 1;
          applyAnimStage(animStage, 1);
          animStage++;
          if (animStage > 2) {
            animStage    = 2;
            animProgress = 1;
            animPlaying  = false;
            // Update button icon to play (not pause)
            const icon = $("playIcon");
            if (icon) icon.innerHTML = '<path d="M8 5v14l11-7z"/>';
          } else {
            animProgress = 0;
          }
        } else {
          applyAnimStage(animStage, animProgress);
        }
      }

      // Camera
      cx += (tx - cx) * 0.08;
      cy += (ty - cy) * 0.08;
      camera.position.z += (zoom - camera.position.z) * 0.12;
      root.rotation.set(cx, cy, 0);
      renderer.render(scene, camera);
    }
    loop();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Wire the play/pause button to the 3-D animation
  // ─────────────────────────────────────────────────────────────────────────
  const btnPlay = $("btnPlay");
  const btnBack = $("btnBack");
  const playIcon = $("playIcon");

  if (btnPlay) {
    btnPlay.addEventListener("click", () => {
      if (!_animState) return;
      if (_animState.isPlaying()) {
        _animState.pause();
        if (playIcon) playIcon.innerHTML = '<path d="M8 5v14l11-7z"/>';
      } else {
        _animState.play();
        if (playIcon) playIcon.innerHTML = '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>';
      }
    });
  }

  if (btnBack) {
    btnBack.addEventListener("click", () => {
      if (_animState) _animState.replay();
      if (playIcon) playIcon.innerHTML = '<path d="M8 5v14l11-7z"/>';
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  loadReaction();
})();

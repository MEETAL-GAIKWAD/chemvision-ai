(function () {
  const api = window.ChemVisionAPI;
  if (!api) return;

  const emailOk = (value) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
  const setHint = (id, message, bad = false) => {
    const hint = document.getElementById(id);
    if (!hint) return;
    hint.className = bad ? "hint bad" : "hint";
    hint.textContent = message;
  };

  const formIn = document.getElementById("formIn");
  if (formIn) {
    formIn.addEventListener(
      "submit",
      async (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        const email = document.getElementById("inEmail").value.trim();
        const password = document.getElementById("inPass").value;
        if (!emailOk(email)) return setHint("hintIn", "Enter a valid email address.", true);
        if (!password) return setHint("hintIn", "Enter your password.", true);

        setHint("hintIn", "Signing in...");
        try {
          const data = await api.login({ email, password });
          api.saveSession(data);
          window.location.href = "dashboard.html";
        } catch (error) {
          setHint("hintIn", error.message, true);
        }
      },
      true
    );
  }

  const formUp = document.getElementById("formUp");
  if (formUp) {
    formUp.addEventListener(
      "submit",
      async (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        const fullName = document.getElementById("upName").value.trim();
        const email = document.getElementById("upEmail").value.trim();
        const password = document.getElementById("upPass").value;
        const terms = document.getElementById("terms");
        if (!fullName) return setHint("hintUp", "Add the name your workspace will use.", true);
        if (!emailOk(email)) return setHint("hintUp", "Enter a valid email address.", true);
        if (password.length < 8) return setHint("hintUp", "Use at least 8 characters.", true);
        if (terms && !terms.checked) return setHint("hintUp", "Accept the terms to continue.", true);

        setHint("hintUp", "Creating your account...");
        try {
          const data = await api.signup({
            full_name: fullName,
            email,
            password,
            field_of_study: "Chemistry",
            institution: "",
            learning_focus: "Reaction visualization",
          });
          api.saveSession(data);
          window.location.href = "dashboard.html";
        } catch (error) {
          setHint("hintUp", error.message, true);
        }
      },
      true
    );
  }
})();

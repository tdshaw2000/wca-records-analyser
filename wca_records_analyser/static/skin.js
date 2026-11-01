// Gear menu: picking a skin saves it (the server sets the cookie) and swaps the skin
// stylesheet in place, so the page is never reloaded. Without this script the form
// still works, with a page reload. Like the other scripts, no styling is set here.
(function () {
  "use strict";

  const picker = document.querySelector(".skin-picker");
  if (!picker) return;
  const form = picker.querySelector(".skin-menu");
  const stylesheet = document.getElementById("theme-stylesheet");

  form.addEventListener("submit", (event) => {
    const choice = event.submitter;
    if (!choice || !stylesheet) return;
    event.preventDefault();
    const data = new FormData(form);
    data.set("skin", choice.value);
    // A saved choice is answered with a redirect, which "manual" leaves opaque. Anything
    // else means it wasn't saved, so fall back to the ordinary post, which shows why.
    fetch(form.action, { method: "POST", body: data, redirect: "manual" })
      .then((response) => {
        if (response.type !== "opaqueredirect") throw new Error("skin not saved");
        stylesheet.href = choice.dataset.themeCss;
        for (const option of form.querySelectorAll(".skin-option")) {
          if (option === choice) option.setAttribute("aria-current", "true");
          else option.removeAttribute("aria-current");
        }
        picker.open = false;
      })
      // Not saved in place: post the form the ordinary way. submit() leaves out the pressed
      // button, so the choice goes in a hidden field.
      .catch(() => {
        const field = document.createElement("input");
        field.type = "hidden";
        field.name = "skin";
        field.value = choice.value;
        form.append(field);
        form.submit();
      });
  });

  // A tap anywhere outside the open menu closes it.
  document.addEventListener("click", (event) => {
    if (picker.open && !picker.contains(event.target)) picker.open = false;
  });
})();

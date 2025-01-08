document.addEventListener("DOMContentLoaded", () => {
  const langButton = document.getElementById("lang-toggle");
  const currentLang = localStorage.getItem("language") || "en";

  // Update the button text based on the current language
  updateButtonText(currentLang);

  // Switch language on button click
  langButton.addEventListener("click", () => {
    const newLang = currentLang === "en" ? "es" : "en";
    localStorage.setItem("language", newLang);
    location.reload(); // Reload the page to apply changes
  });
});

function updateButtonText(lang) {
  const langButton = document.getElementById("lang-toggle");
  langButton.textContent =
    lang === "en" ? "Switch to Español" : "Switch to English";
}

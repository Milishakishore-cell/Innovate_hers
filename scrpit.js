document.addEventListener("DOMContentLoaded", function () {
    const popup = document.getElementById("languagePopup");
    const closePopup = document.getElementById("closePopup");
    const languageSelect = document.getElementById("languageSelect");
    
    // Show the popup on load
    popup.style.display = "block";
    
    closePopup.addEventListener("click", function () {
        popup.style.display = "none";
    });
    
    languageSelect.addEventListener("change", function () {
        const selectedLang = languageSelect.value;
        translatePage(selectedLang);
    });
});

function translatePage(lang) {
    const elements = document.querySelectorAll("[data-translate]");
    const translations = {
        "en": {
            "welcome": "Welcome to Your College Portal",
            "explore": "Explore Now",
            "footer": "© 2025 College Portal | All Rights Reserved"
        },
        "hi": {
            "welcome": "आपके कॉलेज पोर्टल में आपका स्वागत है",
            "explore": "अभी खोजें",
            "footer": "© 2025 कॉलेज पोर्टल | सभी अधिकार सुरक्षित"
        },
        "es": {
            "welcome": "Bienvenido a su portal universitario",
            "explore": "Explorar ahora",
            "footer": "© 2025 Portal Universitario | Todos los derechos reservados"
        }
    };
    
    elements.forEach(el => {
        const key = el.getAttribute("data-translate");
        if (translations[lang] && translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });
}

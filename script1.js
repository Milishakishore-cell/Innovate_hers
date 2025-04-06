

// Typewriter effect on labels
const labels = document.querySelectorAll('.form-control label');

labels.forEach(label => {
    label.innerHTML = label.innerText
        .split('')
        .map((letter, idx) => `<span style="transition-delay:${idx * 50}ms">${letter}</span>`)
        .join('');

    const spans = label.querySelectorAll('span');
    let idx = 0;

    function animate() {
        if (idx < spans.length) {
            spans[idx].classList.add('animated');
            idx++;
            setTimeout(animate, 50); // Adjust timing as needed
        }
    }

    animate();
});

// Form submission logic
document.getElementById("loginForm").addEventListener("submit", function (event) {
    event.preventDefault(); // Prevent default form submission

    const email = document.getElementById("emailInput").value.trim();
    const password = document.getElementById("passwordInput").value.trim();
    const errorMessage = document.getElementById("errorMessage");

    if (!email || !password) {
        errorMessage.textContent = "Both email and password are required!";
        return;
    }

    // Redirect to another page after successful validation
    window.location.href = "map.html"; // Replace with your desired page URL
});


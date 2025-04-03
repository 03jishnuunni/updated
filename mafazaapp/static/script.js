const swiper = new Swiper('.swiper', {
    effect: "coverflow",
    grabCursor: true,
    centeredSlides: true,
    loop: true,
    loopAdditionalSlides: 3,
    slidesPerView: "auto",
    initialSlide: 1,
    coverflowEffect: {
        rotate: 15,
        stretch: 0,
        depth: 300,
        modifier: 1,
        slideShadows: true,
    },
    pagination: {
        el: ".swiper-pagination",
        clickable: true,
    },
    navigation: {
        nextEl: ".swiper-button-next",
        prevEl: ".swiper-button-prev",
    },
    autoplay: {
        delay: 3000,
        disableOnInteraction: false,
    },
    breakpoints: {
        320: {
            slidesPerView: 1.2,
            coverflowEffect: {
                rotate: 10,
                depth: 100,
                stretch: 50,
            }
        },
        768: {
            slidesPerView: 1.8,
            coverflowEffect: {
                rotate: 15,
                depth: 200,
                stretch: 50,
            }
        },
        1024: {
            slidesPerView: 2.2,
            coverflowEffect: {
                rotate: 15,
                depth: 300,
                stretch: 50,
            }
        },
        1400: {
            slidesPerView: 2.5,
            coverflowEffect: {
                rotate: 15,
                depth: 400,
                stretch: 50,
            }
        }
    }
});

// JavaScript for Sidebar Toggle
document.getElementById("toggleSidebar").addEventListener("click", function() {
var sidebar = document.getElementById("sidebar");
var toggleButton = document.getElementById("toggleSidebar");

if (sidebar.style.display === "none" || sidebar.style.display === "") {
sidebar.style.display = "block";  // Show Sidebar
toggleButton.innerHTML = "✖";   // Change to Close Button
} else {
sidebar.style.display = "none";  // Hide Sidebar
toggleButton.innerHTML = "☰";   // Change to Menu Button
}
});



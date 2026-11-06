/* Menú en celular. Es el único comportamiento común del sitio. */
(function () {
  var boton = document.querySelector(".menu-boton"), menu = document.getElementById("menu");
  if (!boton || !menu) return;
  boton.addEventListener("click", function () {
    boton.setAttribute("aria-expanded", String(menu.classList.toggle("abierto")));
  });
})();

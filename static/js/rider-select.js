// Convierte cualquier <select class="rider-select"> en un dropdown filtrable
// (escribe para buscar) pero que SOLO acepta corredores de la lista (create:false).
// Usado tanto en la votación (dashboard) como en el ingreso manual del admin.
document.querySelectorAll('.rider-select').forEach(function (el) {
  new TomSelect(el, {
    create: false,           // no permite texto libre
    allowEmptyOption: true,
    maxOptions: null,
    sortField: { field: 'text', direction: 'asc' }
  });
});

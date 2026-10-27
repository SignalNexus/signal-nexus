(function () {
  var LINK_RE = /^https:\/\/buy\.stripe\.com\/[A-Za-z0-9]+$/;

  function paymentLink(product) {
    if (!product) {
      return "";
    }
    var raw = (product.paymentLink || "").trim();
    return LINK_RE.test(raw) ? raw : "";
  }

  function mount(node, config) {
    if (node.querySelector("a.sn-buy")) {
      return;
    }
    var slug = node.getAttribute("data-product") || "";
    var href = paymentLink((config.products || {})[slug]);
    if (!href) {
      var paragraph = document.createElement("p");
      paragraph.className = "sn-checkout-status";
      paragraph.textContent = "Checkout is not configured.";
      node.appendChild(paragraph);
      return;
    }
    var link = document.createElement("a");
    link.className = "sn-buy";
    link.href = href;
    link.rel = "noopener noreferrer";
    link.textContent = "Continue to Stripe Checkout";
    node.appendChild(link);
  }

  function boot() {
    var config = window.SIGNAL_NEXUS_CHECKOUT || {};
    var nodes = document.querySelectorAll(".sn-checkout[data-product]");
    for (var i = 0; i < nodes.length; i += 1) {
      mount(nodes[i], config);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

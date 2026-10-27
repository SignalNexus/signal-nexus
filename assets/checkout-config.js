/* Stripe Payment Links for the product pages.
   Never put a secret key, a restricted key, or a webhook secret in this file.
   promotionCode charges the Launch Price through 2026-12-31.
   After that date the same paymentLink charges the Regular Price. */
window.SIGNAL_NEXUS_CHECKOUT = {
  launchEndsAt: "2026-12-31T15:00:00.000Z",
  products: {
    starter: {
      paymentLink: "https://buy.stripe.com/eVqdR9dDbg9a3aa8Gw3gk00",
      promotionCode: "LPSTARTER",
    },
    "volume-pack": {
      paymentLink: "https://buy.stripe.com/5kQ9AT2Yx3mo9yyg8Y3gk01",
      promotionCode: "LPVOLUME",
    },
    "profit-pack": {
      paymentLink: "https://buy.stripe.com/28E4gz2Yx5uwbGG4qg3gk02",
      promotionCode: "LPPROFIT",
    },
    complete: {
      paymentLink: "https://buy.stripe.com/5kQ7sLeHff56aCCf4U3gk03",
      promotionCode: "LPCOMP",
    },
  },
};

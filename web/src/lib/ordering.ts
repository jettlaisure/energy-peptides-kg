/* Whether the site takes orders.

   The catalog goes public before the payment processor does: until Kashu attaches the live store we
   run against their sandbox, where any card number is accepted and nothing is charged. That is fine
   on preview and fatal on energypeptides.us, so while the processor is in test mode the site browses
   but does not sell.

   Opening ordering is not a separate switch to remember — it is the launch-checklist step that makes
   the processor live (TAGADA_ENV + PUBLIC_TAGADA_ENV = live). PUBLIC_ORDERING=open forces it on for
   local work and for walking the full flow in a preview build. */
export const orderingOpen =
  import.meta.env.PUBLIC_TAGADA_ENV === 'live' || import.meta.env.PUBLIC_ORDERING === 'open';

/* Shown wherever a buy control would otherwise be. */
export const orderingClosedLine = 'Ordering opens soon';
export const orderingClosedNote =
  'We are completing payment setup, so the catalog is not taking orders yet. Specifications, testing and certificates are all here in the meantime.';

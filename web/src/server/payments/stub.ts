import type { PaymentAdapter } from './types';
/* Stand-in until the Kashu account is live. Approves everything; records nothing outside our own orders table. */
export const stubAdapter: PaymentAdapter = {
  mode: 'stub',
  async charge(req) {
    return { status: 'paid', paymentId: `stub_${req.orderId}`, customerId: `stub_cust_${req.customer.email.toLowerCase()}` };
  },
  async status() { return 'paid'; },
};

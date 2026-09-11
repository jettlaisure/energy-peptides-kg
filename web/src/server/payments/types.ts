export interface ChargeRequest {
  orderId: string;
  amountCents: number;
  currency: string;
  tagadaToken: string;
  scaRequired: boolean;
  customer: { email: string; firstName: string; lastName: string; phone?: string };
  returnUrl: string;
  metadata: Record<string, string>;
  address?: { line1: string; line2?: string; city: string; state: string; postalCode: string; country: string };
}
export type ChargeResult =
  | { status: 'paid'; paymentId: string; customerId?: string }
  | { status: 'requires_action'; paymentId: string; customerId?: string; redirectUrl: string }
  | { status: 'failed'; paymentId?: string; error: string };

export interface PaymentAdapter {
  readonly mode: 'stub' | 'tagada';
  charge(req: ChargeRequest): Promise<ChargeResult>;
  status(paymentId: string): Promise<'paid' | 'pending' | 'failed'>;
}

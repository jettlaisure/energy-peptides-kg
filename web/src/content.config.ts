import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

/* Optional approved copy written through the /new-product-page task graph. A file at
   ../site/pages/products/<slug>.md (front-matter `product: "<Product name>"`) is rendered in the
   product's Overview. Drafts (*.draft.md) are ignored until approved and renamed. */
const productCopy = defineCollection({
  loader: glob({ base: '../site/pages/products', pattern: ['*.md', '!*.draft.md'] }),
  schema: z.object({ product: z.string(), title: z.string().optional(), generated_at: z.string().optional() }),
});

export const collections = { productCopy };

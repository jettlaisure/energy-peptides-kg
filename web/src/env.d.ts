/// <reference types="astro/client" />
interface ImportMetaEnv { readonly PUBLIC_PAYMENT_MODE?: string; readonly PUBLIC_TOKENIZER_ENV?: string; readonly PUBLIC_TAGADA_ENV?: string; }
interface ImportMeta { readonly env: ImportMetaEnv; }

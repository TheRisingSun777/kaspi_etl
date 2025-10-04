// lib/types.ts
export type Seller = {
  name: string;
  price: number;               // in KZT
  deliveryDate?: string;       // normalized human text
  isPriceBot?: boolean;        // heuristic
};

export type Variant = {
  productId: string;           // Kaspi product (variant) ID
  label: string;               // size/variant label or fallback
  variantColor?: string;
  variantSize?: string;
  rating?: { avg?: number; count?: number };
  reviewsCount?: number;
  reviewDateOldest?: string;
  reviewDateLatest?: string;
  productUrl?: string;
  sellersCount: number;
  sellers: Seller[];
  stats?: {
    min?: number;
    median?: number;
    max?: number;
    spread?: number;           // max - min
    stddev?: number;
    predictedMin24h?: number;
    predictedMin7d?: number;
    stabilityScore?: number;
  };
};

export type AnalyzeResult = {
  masterProductId: string;
  productName?: string;
  cityId: string;
  productImageUrl?: string;
  attributes?: { sizesAll?: string[]; colorsAll?: string[] };
  variantMap?: Record<string, { color?: string; size?: string; name?: string }>;
  ratingCount?: number;
  variants: Variant[];

  // derived
  uniqueSellers?: number;
  fastestDelivery?: string;
  analytics?: {
    avgSpread?: number;
    medianSpread?: number;
    maxSpread?: number;
    botShare?: number;                // 0..1
    attractivenessIndex?: number;     // 0..100
    stabilityScore?: number;          // 0..100
    bestEntryPrice?: number;          // suggested buy-box price
  };
};

// Back-compat aliases used by components
export type SellerInfo = Seller;
export type VariantInfo = Variant;
export type AnalyzeResponse = AnalyzeResult;


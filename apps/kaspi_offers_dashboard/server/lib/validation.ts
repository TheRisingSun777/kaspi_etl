import { z } from 'zod'

export const RunInputSchema = z.object({
  merchantId: z.string().min(1).optional(),
  storeId: z.string().min(1).optional(),
  cityId: z.union([z.string(), z.number()]).transform(v=>String(v||'710000000')).optional(),
  sku: z.union([z.string(), z.array(z.string())]).optional(),
  productId: z.union([z.string(), z.number()]).optional(),
  dry: z.union([z.boolean(), z.string()]).optional().transform(v=>String(v) !== 'false'),
  ourPrice: z.union([z.number(), z.string()]).optional().transform(v=>Number(v)),
  opponents: z.array(z.any()).optional(),
})

export type RunInput = z.infer<typeof RunInputSchema>



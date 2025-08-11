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

export const BulkInputSchema = z.object({
  merchantId: z.string().min(1).optional(),
  storeId: z.string().min(1).optional(),
  cityId: z.union([z.string(), z.number()]).transform(v=>String(v||'710000000')).optional(),
  skus: z.array(z.string()).optional(),
  scope: z.enum(["active","filtered"]).optional(),
  chunkSize: z.number().int().min(1).max(500).optional().default(200),
  dry: z.union([z.boolean(), z.string()]).optional().transform(v=>String(v) !== 'false')
})

export type BulkInput = z.infer<typeof BulkInputSchema>

export const ExportQuerySchema = z.object({
  merchantId: z.string().optional(),
  storeId: z.string().optional(),
  cityId: z.union([z.string(), z.number()]).optional(),
  format: z.enum(['csv','xlsx']).default('csv')
})

export const SettingsPostSchema = z.object({
  merchantId: z.string().optional(),
  storeId: z.string().optional(),
  updates: z.record(z.object({
    active: z.boolean().optional(),
    min: z.number().optional(),
    max: z.number().optional(),
    step: z.number().optional(),
    interval: z.number().optional(),
    ignoredOpponents: z.array(z.string()).optional(),
    // v2 keys
    minPrice: z.number().optional(),
    maxPrice: z.number().optional(),
    stepKzt: z.number().optional(),
    intervalMin: z.number().optional(),
    ignoreSellers: z.array(z.string()).optional(),
  })).optional(),
  items: z.record(z.object({
    active: z.boolean().optional(),
    min: z.number().optional(),
    max: z.number().optional(),
    step: z.number().optional(),
    interval: z.number().optional(),
  })).optional(),
  globalIgnore: z.array(z.string()).optional(),
  global: z.object({ ignoreSellers: z.array(z.string()).optional() }).optional(),
})

export const ImportRowSchema = z.object({
  sku: z.string().min(1),
  min: z.number().optional(),
  max: z.number().optional(),
  step: z.number().optional(),
  active: z.boolean().optional(),
})



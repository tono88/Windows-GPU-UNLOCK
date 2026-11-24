/* GPL-2.0-only. This inventory has no write-enabled build mode. */
#pragma once
#if !defined(GU_DIAGNOSTIC_ONLY) || !defined(GU_DIAGNOSTIC_PROBE) || !defined(GU_PROBE_GENERIC)
#error FX516PE inventory requires the diagnostic-only generic graph
#endif
#if defined(GU_FULL_UNLOCK) || defined(GU_EXPERIMENTAL_3090) || defined(GU_UEFI_PORT) || defined(GU_INTERNAL_BOOT) || defined(GU_CONSOLE_PREPARE) || defined(GU_AUTOMATIC_BOOT) || defined(GU_HEADLESS_RESEARCH) || defined(GU_PROBE_PARENT_BASELINE) || defined(GU_PROBE_DUMP_PROM)
#error FX516PE inventory cannot be combined with GPU writes, release, reset or deep capture
#endif
#define GU_FX_PCI_ID 0x25a010deU
#define GU_FX_SUBSYSTEM 0x13dc1043U
static inline int GuFxInventoryIdentity(unsigned int id,unsigned int subsystem,unsigned int cls) {
  return id==GU_FX_PCI_ID && subsystem==GU_FX_SUBSYSTEM && (cls>>24)==3U;
}

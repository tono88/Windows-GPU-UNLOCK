/* GPL-2.0-only. RAM-only protocol mocks; no physical GPU or firmware access. */
#define main UpstreamFixtureMain
#include "../../internal-boot/boot/test_probe.c"
#undef main
#include "inventory_policy.h"

static UINT32 FxId,FxSubsystem,FxCommand;
static int FxReads,FxDrift,FxAttrCalls,FxAttrWrites;
static EFI_STATUS EFIAPI FxRead(EFI_PCI_IO_PROTOCOL *io,EFI_PCI_IO_PROTOCOL_WIDTH width,UINT32 at,UINTN n,VOID *data) {
  (void)io;
  if(width!=EfiPciIoWidthUint32)return EFI_UNSUPPORTED;
  if(at==0 && n==1){*(UINT32 *)data=FxId;return EFI_SUCCESS;}
  if(at==8 && n==1){*(UINT32 *)data=0x030000a1U;return EFI_SUCCESS;}
  if(at==0 && n==64) {
    FxReads++;
    if(S.Scenario==SC_CFG_FAIL){((UINT32 *)data)[0]=FxId;return EFI_DEVICE_ERROR;}
    memset(data,0,n*sizeof(UINT32));UINT32 *v=data;
    v[0]=FxId;v[1]=FxCommand;v[2]=0x030000a1U;v[11]=FxSubsystem;
    if(FxDrift && FxReads>1)v[1]^=1U;
    return EFI_SUCCESS;
  }
  return EFI_UNSUPPORTED;
}
static EFI_STATUS EFIAPI FxAttributes(EFI_PCI_IO_PROTOCOL *io,EFI_PCI_IO_PROTOCOL_ATTRIBUTE_OPERATION op,UINT64 mask,UINT64 *result) {
  (void)io;
  if(op!=EfiPciIoAttributeOperationGet || mask || !result){FxAttrWrites++;return EFI_UNSUPPORTED;}
  FxAttrCalls++;*result=0;return EFI_SUCCESS;
}
static EFI_STATUS FxRun(UINT32 id,UINT32 subsystem,UINT32 command,int drift,int scenario) {
  Setup(scenario);FxId=id;FxSubsystem=subsystem;FxCommand=command;FxDrift=drift;
  FxReads=FxAttrCalls=FxAttrWrites=0;
  Pci.Pci.Read=FxRead;Pci.Attributes=FxAttributes;
  CAPTURE c={0};c.Table=&Table;c.File=&LogFile;c.Complete=TRUE;c.Io=EFI_SUCCESS;
  EFI_STATUS result=GuProbeGpu(&Table,&c);
  Flush(&c);
  Check(!S.RegReads && !S.PromReads && !S.PromAllocs && !FxAttrWrites,"no MMIO, PROM, DMA or PCI attribute writes");
  return result;
}
int main(void) {
  for(UINT32 command=0;command<8;command++) {
    Check(FxRun(GU_FX_PCI_ID,GU_FX_SUBSYSTEM,command,0,SC_OK)==EFI_SUCCESS,"config inventory accepts observed decode bits without changing them");
    Check(FxReads==2 && FxAttrCalls==1,"configuration checked twice around one Get-only attribute observation");
    Check(Logged("config-only=1 can-unlock=0 no-mmio=1 no-prom=1 no-pci-write=1"),"inventory limits recorded");
  }
  Check(FxRun(0x25a210deU,GU_FX_SUBSYSTEM,0,0,SC_OK)==EFI_NOT_READY,"3050 non-Ti is not this target");
  Check(FxRun(GU_FX_PCI_ID,0x13fc1043U,0,0,SC_OK)==EFI_NOT_READY,"other ASUS subsystem refused");
  Check(FxRun(GU_FX_PCI_ID,GU_FX_SUBSYSTEM,0,1,SC_OK)==EFI_NOT_READY,"changing configuration refused");
  Check(FxRun(GU_FX_PCI_ID,GU_FX_SUBSYSTEM,0,0,SC_CFG_FAIL)==EFI_NOT_READY,"failed partial config read refused");
  Check(!FxAttrCalls,"failed config read never reaches attribute observation");
  printf("PASS FX516PE inventory: %d RAM-only checks\n",Checks);
  return 0;
}

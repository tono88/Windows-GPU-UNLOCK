/* GPL-2.0-only. FX516PE config/ownership inventory. No MMIO, PROM or GPU writes. */
#include <Uefi.h>
#include <Protocol/PciIo.h>
#include "../../internal-boot/boot/diagnostic.h"
#include "inventory_policy.h"

VOID Text(CAPTURE *,const char *);
VOID Hex(CAPTURE *,UINT64,UINTN);
VOID End(CAPTURE *);
VOID Problem(CAPTURE *,const char *,EFI_STATUS);

static EFI_GUID PciGuid=EFI_PCI_IO_PROTOCOL_GUID;

EFI_STATUS GuProbeGpu(EFI_SYSTEM_TABLE *table,CAPTURE *c) {
  if(!table || !table->BootServices || !c)return EFI_INVALID_PARAMETER;
  EFI_BOOT_SERVICES *bs=table->BootServices;
  EFI_LOCATE_HANDLE_BUFFER locate=bs->LocateHandleBuffer;
  EFI_HANDLE_PROTOCOL handle=bs->HandleProtocol;
  EFI_FREE_POOL release=bs->FreePool;
  if(!locate || !handle || !release)return EFI_UNSUPPORTED;
  EFI_HANDLE *all=NULL;UINTN count=0,candidates=0;
  EFI_PCI_IO_PROTOCOL *target=NULL;EFI_HANDLE targetHandle=NULL;
  EFI_STATUS s=locate(ByProtocol,&PciGuid,NULL,&count,&all);
  if(s!=EFI_SUCCESS || !all || count>1024) {
    if(all)release(all);
    Problem(c,"fx-pci-inventory",EFI_NOT_READY);return EFI_NOT_READY;
  }
  BOOLEAN valid=TRUE;
  for(UINTN i=0;i<count;i++) {
    EFI_PCI_IO_PROTOCOL *io=NULL;UINT32 id=0,cls=0;
    if(handle(all[i],&PciGuid,(VOID **)&io)!=EFI_SUCCESS || !io || !io->Pci.Read ||
       io->Pci.Read(io,EfiPciIoWidthUint32,0,1,&id)!=EFI_SUCCESS){valid=FALSE;continue;}
    if((id&0xffffU)!=0x10deU)continue;
    if(io->Pci.Read(io,EfiPciIoWidthUint32,8,1,&cls)!=EFI_SUCCESS){valid=FALSE;continue;}
    if((cls>>24)!=3)continue;
    candidates++;
    if(id==GU_FX_PCI_ID){target=io;targetHandle=all[i];}
  }
  if(!valid || candidates!=1 || !target) {
    release(all);Problem(c,"fx-exact-single-gpu",EFI_UNSUPPORTED);return EFI_NOT_READY;
  }
  EFI_PCI_IO_PROTOCOL_CONFIG read=target->Pci.Read;
  EFI_PCI_IO_PROTOCOL_GET_LOCATION location=target->GetLocation;
  EFI_PCI_IO_PROTOCOL_ATTRIBUTES attributes=target->Attributes;
  UINT32 before[64],after[64];
  for(UINTN i=0;i<64;i++){before[i]=0xa5a5a5a5U;after[i]=0x5a5a5a5aU;}
  UINTN segment=0,bus=0,device=0,function=0;
  if(!location || location(target,&segment,&bus,&device,&function)!=EFI_SUCCESS ||
     segment>0xffffU || bus>255 || device>31 || function>7 ||
     read(target,EfiPciIoWidthUint32,0,64,before)!=EFI_SUCCESS ||
     !GuFxInventoryIdentity(before[0],before[11],before[2])) {
    release(all);Problem(c,"fx-identity-or-config",EFI_NOT_READY);return EFI_NOT_READY;
  }
  UINT64 attrs=0;
  EFI_STATUS attrStatus=attributes?attributes(target,EfiPciIoAttributeOperationGet,0,&attrs):EFI_UNSUPPORTED;
  EFI_PCI_IO_PROTOCOL *same=NULL;
  UINTN seg2=0,bus2=0,dev2=0,fun2=0;
  valid=table->BootServices==bs && bs->HandleProtocol==handle &&
    bs->LocateHandleBuffer==locate && bs->FreePool==release &&
    target->Pci.Read==read && target->GetLocation==location && target->Attributes==attributes;
  if(valid)valid=handle(targetHandle,&PciGuid,(VOID **)&same)==EFI_SUCCESS && same==target &&
    table->BootServices==bs && bs->HandleProtocol==handle && bs->FreePool==release &&
    target->Pci.Read==read && target->GetLocation==location && target->Attributes==attributes;
  if(valid)valid=location(target,&seg2,&bus2,&dev2,&fun2)==EFI_SUCCESS &&
    segment==seg2 && bus==bus2 && device==dev2 && function==fun2 &&
    read(target,EfiPciIoWidthUint32,0,64,after)==EFI_SUCCESS;
  if(valid)for(UINTN i=0;i<64;i++)if(before[i]!=after[i]){valid=FALSE;break;}
  if(!valid){release(all);Problem(c,"fx-observation-changed",EFI_NOT_READY);return EFI_NOT_READY;}
  Text(c,"fx516pe-330 config-only=1 can-unlock=0 no-mmio=1 no-prom=1 no-pci-write=1");End(c);
  Text(c,"fx-target segment=0x");Hex(c,segment,4);Text(c," bus=0x");Hex(c,bus,2);
  Text(c," device=0x");Hex(c,device,2);Text(c," function=0x");Hex(c,function,2);End(c);
  Text(c,"fx-config dwords=");for(UINTN i=0;i<64;i++){Hex(c,before[i],8);Text(c," ");}End(c);
  Text(c,"fx-attributes status=0x");Hex(c,attrStatus,16);Text(c," value=0x");Hex(c,attrs,16);End(c);
  Text(c,"fx-decode memory=");Hex(c,(before[1]>>1)&1U,1);
  Text(c," bus-master=");Hex(c,(before[1]>>2)&1U,1);End(c);
  Text(c,"fx-bios-validation=pending; compare with local Windows inventory");End(c);
  s=release(all);
  if(s!=EFI_SUCCESS){Problem(c,"fx-pci-free",s);return s;}
  return c->Io;
}

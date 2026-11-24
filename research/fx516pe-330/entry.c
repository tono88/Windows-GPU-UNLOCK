/* GPL-2.0-only. Launch-volume logging only; returns to firmware without chainloading. */
#include <Uefi.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
#include "../../internal-boot/boot/diagnostic.h"
#include "inventory_policy.h"
#include "usb_media.h"

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image,EFI_SYSTEM_TABLE *table);
/* Keep one checked absolute pointer so the image carries explicit PE relocations. */
static EFI_STATUS (EFIAPI * volatile EntryPin)(EFI_HANDLE,EFI_SYSTEM_TABLE *)=efi_main;

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image,EFI_SYSTEM_TABLE *table) {
  if(EntryPin!=efi_main)return EFI_COMPROMISED_DATA;
  if(!table || !table->BootServices || !table->ConOut || !table->ConOut->OutputString)return EFI_INVALID_PARAMETER;
  EFI_GUID loadedGuid=EFI_LOADED_IMAGE_PROTOCOL_GUID;
  EFI_GUID fsGuid=EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
  EFI_GUID pathGuid=EFI_DEVICE_PATH_PROTOCOL_GUID;
  EFI_LOADED_IMAGE_PROTOCOL *loaded=NULL;
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *fs=NULL;
  EFI_FILE_PROTOCOL *root=NULL,*directory=NULL,*log=NULL;
  EFI_STATUS s=table->BootServices->HandleProtocol(image,&loadedGuid,(VOID **)&loaded);
  if(s!=EFI_SUCCESS || !loaded || !loaded->DeviceHandle)return EFI_NOT_FOUND;
  EFI_DEVICE_PATH_PROTOCOL *path=NULL;
  s=table->BootServices->HandleProtocol(loaded->DeviceHandle,&pathGuid,(VOID **)&path);
  if(s!=EFI_SUCCESS || !GuFxUsbPath(path))return EFI_UNSUPPORTED;
  s=table->BootServices->HandleProtocol(loaded->DeviceHandle,&fsGuid,(VOID **)&fs);
  if(s!=EFI_SUCCESS || !fs || !fs->OpenVolume)return EFI_NOT_FOUND;
  s=fs->OpenVolume(fs,&root);
  if(s!=EFI_SUCCESS || !root || !root->Open || !root->Close)return EFI_NOT_FOUND;
  table->ConOut->OutputString(table->ConOut,L"FX516PE BIOS 330 research: CONFIG INVENTORY ONLY\r\nNo GPU writes, MMIO, PROM, reset, driver release or boot changes.\r\n");
  s=root->Open(root,&directory,L"\\FX516PE-INVENTORY",EFI_FILE_MODE_READ|EFI_FILE_MODE_WRITE|EFI_FILE_MODE_CREATE,EFI_FILE_DIRECTORY);
  if(s!=EFI_SUCCESS || !directory || !directory->Open || !directory->Close) {
    root->Close(root);return EFI_DEVICE_ERROR;
  }
  CHAR16 name[]=L"DIAG00.TXT";
  for(UINTN i=0;i<100;i++) {
    name[4]=(CHAR16)('0'+i/10);name[5]=(CHAR16)('0'+i%10);
    EFI_FILE_PROTOCOL *prior=NULL;
    s=directory->Open(directory,&prior,name,EFI_FILE_MODE_READ,0);
    if(s==EFI_SUCCESS && prior) {if(prior->Close)prior->Close(prior);continue;}
    if(s!=EFI_NOT_FOUND || prior){s=EFI_DEVICE_ERROR;break;}
    s=directory->Open(directory,&log,name,EFI_FILE_MODE_READ|EFI_FILE_MODE_WRITE|EFI_FILE_MODE_CREATE,0);
    break;
  }
  if(s!=EFI_SUCCESS || !log || !log->Close) {
    directory->Close(directory);root->Close(root);return EFI_DEVICE_ERROR;
  }
  s=GuCaptureGraphOnVolume(table,log,NULL);
  EFI_STATUS closed=log->Close(log);
  if(s==EFI_SUCCESS && closed!=EFI_SUCCESS)s=closed;
  closed=directory->Close(directory);
  if(s==EFI_SUCCESS && closed!=EFI_SUCCESS)s=closed;
  closed=root->Close(root);
  if(s==EFI_SUCCESS && closed!=EFI_SUCCESS)s=closed;
  table->ConOut->OutputString(table->ConOut,s==EFI_SUCCESS?
    L"Inventory saved in FX516PE-INVENTORY. This is NOT unlock eligibility.\r\n":
    L"Inventory incomplete. Preserve the log for review. No unlock was attempted.\r\n");
  return s;
}

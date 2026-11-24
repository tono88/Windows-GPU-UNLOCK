/* GPL-2.0-only. Conservative USB launch-path check; no partition identifiers. */
#pragma once
#include <Uefi.h>
#include <Protocol/DevicePath.h>
static inline BOOLEAN GuFxUsbPath(const EFI_DEVICE_PATH_PROTOCOL *p) {
  UINTN total=0;BOOLEAN usb=FALSE;
  if(!p)return FALSE;
  for(UINTN nodes=0;nodes<64 && total+4<=4096;nodes++) {
    UINTN n=p->Length[0]+((UINTN)p->Length[1]<<8);
    if(n<4 || n>4096-total)return FALSE;
    if(p->Type==END_DEVICE_PATH_TYPE)
      return n==4 && p->SubType==END_ENTIRE_DEVICE_PATH_SUBTYPE && usb;
    if(p->Type==MESSAGING_DEVICE_PATH && p->SubType==MSG_USB_DP && n==sizeof(USB_DEVICE_PATH))usb=TRUE;
    total+=n;p=(const VOID *)((const UINT8 *)p+n);
  }
  return FALSE;
}

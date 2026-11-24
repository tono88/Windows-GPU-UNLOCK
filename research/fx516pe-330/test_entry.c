/* GPL-2.0-only. Simulate launch media and files in RAM; never run EFI firmware. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef NULL
#include "entry.c"

static EFI_SYSTEM_TABLE T;
static EFI_BOOT_SERVICES B;
static EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL Console;
static EFI_LOADED_IMAGE_PROTOCOL Image;
static EFI_SIMPLE_FILE_SYSTEM_PROTOCOL Fs;
static EFI_FILE_PROTOCOL Root,Dir,Log,Prior;
static struct {USB_DEVICE_PATH Usb;EFI_DEVICE_PATH_PROTOCOL End;} Media;
static int Scenario,Opens,Creates,Captures,ExistingCloses,TestChecks;

static void Assert(int condition,const char *name) {
  TestChecks++;if(!condition){fprintf(stderr,"FAIL entry: %s scenario=%d\n",name,Scenario);exit(1);}
}
static EFI_STATUS EFIAPI Output(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *self,CHAR16 *s){(void)self;(void)s;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Close(EFI_FILE_PROTOCOL *self) {
  if(self==&Prior)ExistingCloses++;
  return self==&Log && Scenario==4?EFI_DEVICE_ERROR:EFI_SUCCESS;
}
static EFI_STATUS EFIAPI Open(EFI_FILE_PROTOCOL *self,EFI_FILE_PROTOCOL **out,CHAR16 *name,UINT64 mode,UINT64 attr) {
  (void)attr;Opens++;*out=NULL;
  if(self==&Root){*out=&Dir;return EFI_SUCCESS;}
  if(self!=&Dir)return EFI_DEVICE_ERROR;
  if(!(mode&EFI_FILE_MODE_WRITE)) {
    if(Scenario==3)return EFI_DEVICE_ERROR;
    if(Scenario==2 || (Scenario==1 && name[4]=='0' && name[5]=='0')){*out=&Prior;return EFI_SUCCESS;}
    return EFI_NOT_FOUND;
  }
  Creates++;*out=&Log;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI Volume(EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *self,EFI_FILE_PROTOCOL **out){(void)self;*out=&Root;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Protocol(EFI_HANDLE h,EFI_GUID *g,VOID **out) {
  (void)h;EFI_GUID loaded=EFI_LOADED_IMAGE_PROTOCOL_GUID,fs=EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID,path=EFI_DEVICE_PATH_PROTOCOL_GUID;
  if(!memcmp(g,&loaded,sizeof(*g))){*out=&Image;return EFI_SUCCESS;}
  if(!memcmp(g,&fs,sizeof(*g))){*out=&Fs;return EFI_SUCCESS;}
  if(!memcmp(g,&path,sizeof(*g))){*out=&Media;return EFI_SUCCESS;}
  return EFI_NOT_FOUND;
}
EFI_STATUS GuCaptureGraphOnVolume(EFI_SYSTEM_TABLE *table,EFI_FILE_PROTOCOL *log,EFI_FILE_PROTOCOL *root) {
  Assert(table==&T && log==&Log && !root,"only the new log reaches capture; firmware dumps disabled");
  Captures++;return Scenario==5?EFI_NOT_READY:EFI_SUCCESS;
}
static EFI_STATUS Run(int scenario) {
  Scenario=scenario;Opens=Creates=Captures=ExistingCloses=0;
  memset(&T,0,sizeof(T));memset(&B,0,sizeof(B));memset(&Media,0,sizeof(Media));
  T.BootServices=&B;T.ConOut=&Console;Console.OutputString=Output;
  B.HandleProtocol=Protocol;Image.DeviceHandle=(VOID *)2;Fs.OpenVolume=Volume;
  Root.Open=Dir.Open=Open;Root.Close=Dir.Close=Log.Close=Prior.Close=Close;
  Media.Usb.Header.Type=MESSAGING_DEVICE_PATH;Media.Usb.Header.SubType=MSG_USB_DP;
  Media.Usb.Header.Length[0]=sizeof(USB_DEVICE_PATH);
  Media.End.Type=END_DEVICE_PATH_TYPE;Media.End.SubType=END_ENTIRE_DEVICE_PATH_SUBTYPE;Media.End.Length[0]=4;
  if(scenario==6)Media.Usb.Header.Type=HARDWARE_DEVICE_PATH;
  if(scenario==7)Media.Usb.Header.Length[0]=1;
  if(scenario==8)Media.End.SubType=END_INSTANCE_DEVICE_PATH_SUBTYPE;
  return efi_main((VOID *)1,&T);
}
int main(void) {
  Assert(Run(0)==EFI_SUCCESS && Creates==1 && Captures==1,"new USB inventory log created");
  Assert(Run(1)==EFI_SUCCESS && ExistingCloses==1 && Creates==1,"existing log skipped and closed");
  Assert(Run(2)==EFI_DEVICE_ERROR && !Creates && !Captures,"100 existing logs are never overwritten");
  Assert(Run(3)==EFI_DEVICE_ERROR && !Creates && !Captures,"presence-read failure prevents creation");
  Assert(Run(4)==EFI_DEVICE_ERROR,"close failure cannot claim success");
  Assert(Run(5)==EFI_NOT_READY,"incomplete capture cannot claim success");
  for(int mode=6;mode<=8;mode++)Assert(Run(mode)==EFI_UNSUPPORTED && !Opens,"internal, malformed or multi-instance path rejected before file access");
  printf("PASS FX516PE entry: %d RAM-only checks\n",TestChecks);
  return 0;
}

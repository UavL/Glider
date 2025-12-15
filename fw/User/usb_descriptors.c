/*
* The MIT License (MIT)
*
* Copyright (c) 2019 Ha Thach (tinyusb.org)
*
* Permission is hereby granted, free of charge, to any person obtaining a copy
* of this software and associated documentation files (the "Software"), to deal
* in the Software without restriction, including without limitation the rights
* to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
* copies of the Software, and to permit persons to whom the Software is
* furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in
* all copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
* IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
* FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
* LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
* OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
* THE SOFTWARE.
*
*/

#include "tusb.h"
#include "platform.h"
#include "board.h"

#define USB_VID   0x1209
// PID assigned to Modos Glider. You may use this PID only if you do not make
// any changes to the USB descriptor (otherwise it might confuses OS)
#define USB_PID   0xAE86
#define USB_BCD   0x0200

//--------------------------------------------------------------------+
// Device Descriptors
//--------------------------------------------------------------------+
tusb_desc_device_t const desc_device =
{
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = USB_BCD,

    // Use Interface Association Descriptor (IAD) for CDC
    // As required by USB Specs IAD's subclass must be common class (2) and protocol must be IAD (1)
    .bDeviceClass       = 0x00,
    .bDeviceSubClass    = 0x00,
    .bDeviceProtocol    = 0x00,
    .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,

    .idVendor           = USB_VID,
    .idProduct          = USB_PID,
    .bcdDevice          = 0x0100,

    .iManufacturer      = 0x01,
    .iProduct           = 0x02,
    .iSerialNumber      = 0x03,

    .bNumConfigurations = 0x01
};

// Invoked when received GET DEVICE DESCRIPTOR
// Application return pointer to descriptor
uint8_t const * tud_descriptor_device_cb(void)
{
  return (uint8_t const *) &desc_device;
}

//--------------------------------------------------------------------+
// HID Report Descriptor
//--------------------------------------------------------------------+

#define FINGER_LOGICAL_COLLECTION   \
  0x05, 0x0d,                     /*   USAGE_PAGE (Digitizers)            */ \
  0x09, 0x22,                     /*   USAGE (Finger)                     */ \
  0xa1, 0x02,                     /*     COLLECTION (Logical)             */ \
  0x09, 0x42,                     /*       USAGE (Tip Switch)             */ \
  0x25, 0x01,                     /*       LOGICAL_MAXIMUM (1)            */ \
  0x75, 0x01,                     /*       REPORT_SIZE (1)                */ \
  0x95, 0x01,                     /*       REPORT_COUNT (1)               */ \
  0x81, 0x02,                     /*       INPUT (Data,Var,Abs)           */ \
  0x75, 0x07,                     /*       REPORT_SIZE (7)                */ \
  0x81, 0x03,                     /*       INPUT (Cnst,Ary,Abs)           */ \
  0x09, 0x51,                     /*       USAGE (Contact Identifier)     */ \
  0x25, 0x0a,                     /*       LOGICAL_MAXIMUM (10)           */ \
  0x75, 0x08,                     /*       REPORT_SIZE (8)                */ \
  0x95, 0x01,                     /*       REPORT_COUNT (1)               */ \
  0x81, 0x02,                     /*       INPUT (Data,Var,Abs)           */ \
  0x05, 0x01,                     /*       USAGE_PAGE (Generic Desktop)   */ \
  0x09, 0x30,                     /*       USAGE (X)                      */ \
  0xa4,                           /*       PUSH                           */ \
  0x26, 0x7f, 0x0c,               /*       LOGICAL_MAXIMUM (3199)         */ \
  0x75, 0x10,                     /*       REPORT_SIZE (16)               */ \
  0x55, 0x0e,                     /*       UNIT_EXPONENT (-2)             */ \
  0x65, 0x13,                     /*       UNIT(Inch,EngLinear)           */ \
  0x34,                           /*       PHYSICAL_MINIMUM (0)           */ \
  0x46, 0x29, 0x04,               /*       PHYSICAL_MAXIMUM (1065)        */ \
  0x95, 0x01,                     /*       REPORT_COUNT (1)               */ \
  0x81, 0x02,                     /*       INPUT (Data,Var,Abs)           */ \
  0x09, 0x31,                     /*       USAGE (Y)                      */ \
  0x26, 0x5f, 0x09,               /*       LOGICAL_MAXIMUM (2399)         */ \
  0x46, 0x1e, 0x03,               /*       PHYSICAL_MAXIMUM (798)         */ \
  0x81, 0x02,                     /*       INPUT (Data,Var,Abs)           */ \
  0xb4,                           /*       POP                            */ \
  0xc0,                           /*     END_COLLECTION                   */

uint8_t const desc_hid_report[] =
{
  0x05, 0x0d,                     /* USAGE_PAGE (Digitizers)              */
  0x09, 0x02,                     /* USAGE (Pen)                          */
  0xa1, 0x01,                     /* COLLECTION (Application)             */
  0x85, REPORT_ID_STYLUS,         /*   REPORT_ID (Pen)                    */
  0x09, 0x20,                     /*   USAGE (Stylus)                     */
  0xa1, 0x02,                     /*   COLLECTION (Physical)              */
  0x35, 0x00,                     /*     PHYSICAL_MINIMUM (0)             */
  0x45, 0x00,                     /*     PHYSICAL_MAXIMUM (0)             */
  0x15, 0x00,                     /*     LOGICAL_MINIMUM (0)              */
  0x25, 0x01,                     /*     LOGICAL_MAXIMUM (1)              */
  0x09, 0x42,                     /*     USAGE (Tip Switch)               */
  0x09, 0x44,                     /*     USAGE (Barrel Switch)            */
  0x09, 0x5a,                     /*     USAGE (Second Barrel Switch)     */
  0x09, 0x45,                     /*     USAGE (Eraser Switch)            */
  0x09, 0x3c,                     /*     USAGE (Invert)                   */
  0x09, 0x32,                     /*     USAGE (In Range)                 */
  0x75, 0x01,                     /*     REPORT_SIZE (1)                  */
  0x95, 0x06,                     /*     REPORT_COUNT (6)                 */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0x75, 0x02,                     /*     REPORT_SIZE (2)                  */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x03,                     /*     INPUT (Cnst,Var,Abs)             */
  0x75, 0x08,                     /*     REPORT_SIZE (8)                  */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x03,                     /*     INPUT (Cnst,Var,Abs)             */
  0xa4,                           /*     PUSH                             */
  0x05, 0x01,                     /*     USAGE_PAGE (Generic Desktop)     */
  0x09, 0x30,                     /*     USAGE (X)                        */
  0x55, 0x0e,                     /*     UNIT_EXPONENT (-2)               */
  0x65, 0x13,                     /*     UNIT (Inch,EngLinear)            */
  0x35, 0x00,                     /*     PHYSICAL_MINIMUM (0)             */
  0x46, 0x29, 0x04,               /*     PHYSICAL_MAXIMUM (1065)          */
  0x26, 0xff, 0x3f,               /*     LOGICAL_MAXIMUM (16383)          */
  0x15, 0x00,                     /*     LOGICAL_MINIMUM (0)              */
  0x75, 0x10,                     /*     REPORT_SIZE (16)                 */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0x09, 0x31,                     /*     USAGE (Y)                        */
  0x46, 0x1e, 0x03,               /*     PHYSICAL_MAXIMUM (798)           */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0xb4,                           /*     POP                              */
  0x05, 0x0d,                     /*     USAGE_PAGE (Digitizers)          */
  0x09, 0x30,                     /*     USAGE (Tip Pressure)             */
  0x65, 0x00,                     /*     Units(None),                     */
  0x15, 0x00,                     /*     LOGICAL_MINIMUM (0)              */
  0x26, 0xff, 0x00,               /*     LOGICAL_MAXIMUM (255)            */
  0x75, 0x08,                     /*     REPORT_SIZE (8)                  */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0xa4,                           /*     PUSH                             */
  0x09, 0x3d,                     /*     USAGE (X Tilt)                   */
  0x09, 0x3e,                     /*     USAGE (Y Tilt)                   */
  0x55, 0x00,                     /*     UNIT_EXPONENT (0)                */
  0x65, 0x14,                     /*     UNIT (Degree)                    */
  0x35, 0xa6,                     /*     PHYSICAL_MINIMUM (-90)           */
  0x45, 0x5a,                     /*     PHYSICAL_MAXIMUM (90)            */
  0x15, 0x81,                     /*     LOGICAL_MINIMUM (-127)           */
  0x25, 0x7f,                     /*     LOGICAL_MAXIMUM (127)            */
  0x95, 0x02,                     /*     REPORT_COUNT (2)                 */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0xb4,                           /*     POP                              */
  0xc0,                           /*   END_COLLECTION                     */
  0xc0,                           /* END_COLLECTION                       */
  // Report for touch screen
  0x05, 0x0d,                     /* USAGE_PAGE (Digitizers)              */
  0x09, 0x04,                     /* USAGE (Touch Screen)                 */
  0xa1, 0x01,                     /* COLLECTION (Application)             */
  0x85, REPORT_ID_TOUCH,          /*   REPORT_ID (Touch)                  */
  0x09, 0xff,                     /*   USAGE (Reserved)                   */
  0x15, 0x00,                     /*   LOGICAL_MINIMUM (0)                */
  0x25, 0x7F,                     /*   LOGICAL_MAXIMUM (127)              */
  0x95, 0x01,                     /*   REPORT_COUNT (1)                   */
  0x75, 0x08,                     /*   REPORT_SIZE (8)                    */
  0x81, 0x03,                     /*   INPUT (Cnst,Var,Abs)               */
  0x09, 0x54,                     /*   USAGE (Contact count)              */
  0x81, 0x02,                     /*   INPUT (Data,Var,Abs)               */
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  FINGER_LOGICAL_COLLECTION
  0x05, 0x0d,                     /*   USAGE_PAGE (Digitizers)            */
  0x85, REPORT_ID_FEATURE,        /*   REPORT_ID (Feature)                */
  0x09, 0x55,                     /*   USAGE(Contact Count Maximum)       */
  0x95, 0x01,                     /*   REPORT_COUNT (1)                   */
  0x25, 0x0a,                     /*   LOGICAL_MAXIMUM (10)               */
  0xb1, 0x02,                     /*   FEATURE (Data,Var,Abs)             */
  0xc0,                           /* END_COLLECTION                       */
  0x05, 0x01,                     /* USAGE_PAGE (Generic Desktop)         */
  0x09, 0x02,                     /* USAGE (Mouse)                        */
  0xA1, 0x01,                     /* COLLECTION (Application)             */
  0x85, REPORT_ID_MOUSE,          /*   REPORT_ID                          */
  0x09, 0x01,                     /*   USAGE (Pointer)                    */  
  0xA1, 0x00,                     /*   COLLECTION (Physical)              */
  0x05, 0x09,                     /*     USAGE_PAGE (Button)              */
  0x19, 0x01,                     /*     USAGE_MINIMUM (Button 1)         */  
  0x29, 0x03,                     /*     USAGE_MAXIMUM (Button 3)         */  
  0x15, 0x00,                     /*     LOGICAL_MINIMUM (0)              */
  0x25, 0x01,                     /*     LOGICAL_MAXIMUM (1)              */  
  0x75, 0x01,                     /*     REPORT_SIZE (1)                  */
  0x95, 0x03,                     /*     REPORT_COUNT (3)                 */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0x75, 0x05,                     /*     REPORT_SIZE (5)                  */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x03,                     /*     INPUT (Cnst,Ary,Abs)             */
  0x75, 0x08,                     /*     REPORT_SIZE (8)                  */
  0x81, 0x03,                     /*     INPUT (Cnst,Ary,Abs)             */
  0x05, 0x01,                     /*     USAGE_PAGE (Generic Desktop)     */
  0x09, 0x30,                     /*     USAGE (X)                        */
  0xa4,                           /*     PUSH                             */
  0x26, 0x7f, 0x0c,               /*     LOGICAL_MAXIMUM (3199)           */
  0x55, 0x0e,                     /*     UNIT_EXPONENT (-2)               */
  0x65, 0x13,                     /*     UNIT(Inch,EngLinear)             */
  0x34,                           /*     PHYSICAL_MINIMUM (0)             */
  0x46, 0x29, 0x04,               /*     PHYSICAL_MAXIMUM (1065)          */
  0x75, 0x10,                     /*     REPORT_SIZE (16)                 */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0x09, 0x31,                     /*     USAGE (Y)                        */
  0x26, 0x5f, 0x09,               /*     LOGICAL_MAXIMUM (2399)           */
  0x46, 0x1e, 0x03,               /*     PHYSICAL_MAXIMUM (798)           */
  0x81, 0x02,                     /*     INPUT (Data,Var,Abs)             */
  0xb4,                           /*     POP                              */
  0x09, 0x38,                     /*     USAGE (Wheel)                    */
  0x15, 0x81,                     /*     LOGICAL_MINIMUM (-127)           */
  0x25, 0x7F,                     /*     LOGICAL_MAXIMUM (127)            */
  0x75, 0x08,                     /*     REPORT_SIZE (8)                  */
  0x95, 0x01,                     /*     REPORT_COUNT (1)                 */
  0x81, 0x06,                     /*     INPUT (Data,Var,Rel)             */
  0xC0,                           /*   END_COLLECTION                     */
  0xC0,                           /* END_COLLECTION                       */
  TUD_HID_REPORT_DESC_GENERIC_INOUT(CFG_TUD_HID_EP_BUFSIZE, HID_REPORT_ID(REPORT_ID_CONTROL))
};

uint8_t const desc_hid_report[] =
{
  TUD_HID_REPORT_DESC_GENERIC_INOUT(CFG_TUD_HID_EP_BUFSIZE)
};

// Invoked when received GET HID REPORT DESCRIPTOR
// Application return pointer to descriptor
// Descriptor contents must exist long enough for transfer to complete
uint8_t const * tud_hid_descriptor_report_cb(uint8_t itf)
{
  (void) itf;
  return desc_hid_report;
}

//--------------------------------------------------------------------+
// Configuration Descriptor
//--------------------------------------------------------------------+
enum
{
  ITF_NUM_HID = 0,
  ITF_NUM_CDC,
  ITF_NUM_CDC_DATA,
  ITF_NUM_TOTAL
};

#define CONFIG_TOTAL_LEN    (TUD_CONFIG_DESC_LEN + TUD_HID_INOUT_DESC_LEN + TUD_CDC_DESC_LEN)

#define EPNUM_HID_OUT     0x01
#define EPNUM_HID_IN      0x81
#define EPNUM_CDC_NOTIF   0x83
#define EPNUM_CDC_OUT     0x02
#define EPNUM_CDC_IN      0x82

uint8_t const desc_fs_configuration[] =
{
  // Config number, interface count, string index, total length, attribute, power in mA
  TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0x00, 200),

  // Interface number, string index, protocol, report descriptor len, EP Out & In address, size & polling interval
  TUD_HID_INOUT_DESCRIPTOR(ITF_NUM_HID, 4, HID_ITF_PROTOCOL_NONE, sizeof(desc_hid_report), EPNUM_HID_OUT, EPNUM_HID_IN, CFG_TUD_HID_EP_BUFSIZE, 2),

  // Interface number, string index, EP notification address and size, EP data address (out, in) and size.
  TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, 5, EPNUM_CDC_NOTIF, 8, EPNUM_CDC_OUT, EPNUM_CDC_IN, 64),
};

// Invoked when received GET CONFIGURATION DESCRIPTOR
// Application return pointer to descriptor
// Descriptor contents must exist long enough for transfer to complete
uint8_t const * tud_descriptor_configuration_cb(uint8_t index)
{
  (void) index; // for multiple configurations

  return desc_fs_configuration;
}

//--------------------------------------------------------------------+
// String Descriptors
//--------------------------------------------------------------------+

// String Descriptor Index
enum {
  STRID_LANGID = 0,
  STRID_MANUFACTURER,
  STRID_PRODUCT,
  STRID_SERIAL,
};

// array of pointer to string descriptors
char const *string_desc_arr[] =
{
  (const char[]) { 0x09, 0x04 }, // 0: is supported language is English (0x0409)
  "Modos",                       // 1: Manufacturer
  "Glider",                      // 2: Product
  NULL,                          // 3: Serials will use unique ID if possible
  "Control",                     // 4: HID Interface
  "Debug",                       // 5: CDC Interface
};

static uint16_t _desc_str[32 + 1];

// Invoked when received GET STRING DESCRIPTOR request
// Application return pointer to descriptor, whose contents must exist long enough for transfer to complete
uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
  (void) langid;
  size_t chr_count;

  switch ( index ) {
    case STRID_LANGID:
      memcpy(&_desc_str[1], string_desc_arr[0], 2);
      chr_count = 1;
      break;

    case STRID_SERIAL:
      chr_count = board_usb_get_serial(_desc_str + 1, 32);
      break;

    default:
      // Note: the 0xEE index string is a Microsoft OS 1.0 Descriptors.
      // https://docs.microsoft.com/en-us/windows-hardware/drivers/usbcon/microsoft-defined-usb-descriptors

      if ( !(index < sizeof(string_desc_arr) / sizeof(string_desc_arr[0])) ) return NULL;

      const char *str = string_desc_arr[index];

      // Cap at max char
      chr_count = strlen(str);
      size_t const max_count = sizeof(_desc_str) / sizeof(_desc_str[0]) - 1; // -1 for string type
      if ( chr_count > max_count ) chr_count = max_count;

      // Convert ASCII string into UTF-16
      for ( size_t i = 0; i < chr_count; i++ ) {
        _desc_str[1 + i] = str[i];
      }
      break;
  }

  // first byte is length (including header), second byte is string type
  _desc_str[0] = (uint16_t) ((TUSB_DESC_STRING << 8) | (2 * chr_count + 2));

  return _desc_str;
}

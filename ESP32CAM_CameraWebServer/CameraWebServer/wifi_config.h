#ifndef WIFI_CONFIG_H
#define WIFI_CONFIG_H

// ============================================================
//  AR Glass 전용 WiFi 설정
//  한 번에 한 보드씩. 먼저 LEFT(0) 를 플래시하고, 오른쪽은 1 로 바꿔 플래시.
// ============================================================

#define WIFI_SSID       "ros5G"
#define WIFI_PASSWORD   "rosrosros"

// 0 = LEFT  (착용자 왼쪽 눈, 192.168.0.137)   <-- 먼저 플래시할 보드
// 1 = RIGHT (착용자 오른쪽 눈, 192.168.0.69)  <-- 나중에 플래시할 보드
#define AR_GLASS_BOARD  0

#if AR_GLASS_BOARD == 1
  #define STATIC_IP_ADDRESS "192.168.0.69"
#else
  #define STATIC_IP_ADDRESS "192.168.0.137"
#endif

#define STATIC_IP_GATEWAY "192.168.0.1"
#define STATIC_IP_NETMASK "255.255.255.0"
#define USE_STATIC_IP 1  // DHCP로 두려면 0

#endif  // WIFI_CONFIG_H
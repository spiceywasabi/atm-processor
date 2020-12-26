// requires Time library and RTCLib
#include <time.h>
#include <TimeLib.h>
#include "RTClib.h"

RTC_DS3231 rtc;

#define RESET 2
#define L1 6
#define L2 7

bool REPEAT = false;
bool DEBUG = false;

String getValue(String data, char separator, int index)
{
  int found = 0;
  int strIndex[] = {0, -1};
  int maxIndex = data.length() - 1;

  for (int i = 0; i <= maxIndex && found <= index; i++) {
    if (data.charAt(i) == separator || i == maxIndex) {
      found++;
      strIndex[0] = strIndex[1] + 1;
      strIndex[1] = (i == maxIndex) ? i + 1 : i;
    }
  }

  return found > index ? data.substring(strIndex[0], strIndex[1]) : "";
}

void setup () {
  // setup pins
  pinMode(L1, OUTPUT);
  pinMode(L2, OUTPUT);
  pinMode(RESET, OUTPUT);
  digitalWrite(RESET, LOW);
  
  // and away we go
  Serial.begin(9600);
  if (! rtc.begin()) {
    Serial.println("Couldn't find RTC");
    Serial.flush();
    abort();
  }

  if (rtc.lostPower()) {
    Serial.println("RTC lost power, let's set the time!");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
}


void prettyPrint(int num){
  if(num>9){
    Serial.print(num);
  } else {
    Serial.print(F("0"));
    Serial.print(num,DEC);
  }
}

void timeString(bool prefix = true) {
  DateTime now = rtc.now();
  // FORMAT: YYYY-MM-DD hh:mm[:ss]
  if (prefix) {
    Serial.print(F("G:"));
  }
  prettyPrint(now.year());
  Serial.print(F("-"));
  prettyPrint(now.month());
  Serial.print(F("-"));
  prettyPrint(now.day());
  Serial.print(F(" "));
  prettyPrint(now.hour());
  Serial.print(F(":"));
  prettyPrint(now.minute());
  Serial.print(F(":"));
  prettyPrint(now.second());
  Serial.println();
}

void loop () {
  if(REPEAT){
    timeString();
  }
  while (Serial.available() == 0) { }
  String input = Serial.readString();
  input.trim();
  String command = getValue(input, '!', 0);
  //command = command.substring(0,command.length()-1);
  if (DEBUG) {
    Serial.print(F("Command: '"));
    Serial.print(command);
    Serial.println(F("'"));
  }
  if (command == "SET") {
    String value = getValue(input, '!', 1);
    char charBuf[value.length() + 2];
    value.toCharArray(charBuf, value.length() + 1);
    int tyear, tday, tmonth, tminute, tsecond, thour;
    byte ret = sscanf(charBuf, "%4d-%2d-%2dT%2d:%2d:%2d",
                      &tyear, &tmonth, &tday, &thour, &tminute, &tsecond);
    if (ret != 7) {
      printf("Error while parsing time");
    }
    // set now
    if (DEBUG) {
      Serial.print(F("RAW: ("));
      Serial.print(value.length());
      Serial.print(F(") "));
      Serial.println(charBuf);
      Serial.print("Date - ");
      Serial.print(F(" year:"));
      Serial.print(tyear);
      Serial.print(F(" day:"));
      Serial.print(tday);
      Serial.print(F(" month:"));
      Serial.print(tmonth);
      Serial.print(F(" hour:"));
      Serial.print(thour);
      Serial.print(F(" minute: "));
      Serial.print(tminute);
      Serial.print(F(" second: "));
      Serial.print(tsecond);
      Serial.println(F("\n"));
    }
    rtc.adjust(DateTime(tyear, tmonth, tday, thour, tminute, tsecond));
  } else if (command == "L1") {
    String value = getValue(input, '!', 1);
    bool v = (bool)value.toInt();
    if (v) {
      digitalWrite(L1, HIGH);
      if (DEBUG) {
        Serial.println(F("L1:ON"));
      }
    } else {
      digitalWrite(L1, LOW);
      if (DEBUG) {
        Serial.println(F("L1:OFF"));
      }
    }
  } else if (command == "L2") {
    String value = getValue(input, '!', 1);
    bool v = (bool)value.toInt();
    if (v) {
      digitalWrite(L2, HIGH);
      if (DEBUG) {
        Serial.println(F("L2:ON"));
      }
    } else {
      digitalWrite(L2, LOW);
      if (DEBUG) {
        Serial.println(F("L2:OFF"));
      }
    }
  } else if (command == "GET") {
    timeString();
  } else if (command == "RESET") {
    Serial.println(F("RESETTING!"));
    delay(1000);
    digitalWrite(RESET, HIGH);
  } else if (command == "DEBUG") {
    if (DEBUG) {
      DEBUG = false;
      Serial.println(F("DEBUG OFF"));
    } else {
      DEBUG = true;
      Serial.println(F("DEBUG ON"));
    }
  } else if (command == "TEMP") {
    Serial.print(F("TEMP:"));
    Serial.print(rtc.getTemperature());
    Serial.println("");
  } else {
    Serial.println(F("UNKNOWN"));
  }
  if(REPEAT){
    delay(3000);
  }
}

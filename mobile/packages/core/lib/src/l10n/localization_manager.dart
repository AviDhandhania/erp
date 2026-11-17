// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:ui';

/// Multilingual Localization Manager for Field Operations across India.
class ClothingLocalizationManager {
  static const List<Locale> supportedLocales = [
    Locale('en', 'US'), // English (Default)
    Locale('hi', 'IN'), // Hindi
    Locale('mr', 'IN'), // Marathi
    Locale('ta', 'IN'), // Tamil
    Locale('bn', 'IN'), // Bengali
  ];

  static const Map<String, Map<String, String>> _translations = {
    'en': {
      'app_title': 'Clothing ERP',
      'scan_barcode': 'Scan Barcode',
      'offline_banner': 'Offline Mode: Changes will sync automatically.',
      'syncing': 'Synchronizing queued changes...',
      'session_expired': 'Session expired. Please log in again.',
      'conflict_alert': 'Sync Conflict: Record was modified on server.',
      'discard': 'Discard',
      'retry': 'Retry',
    },
    'hi': {
      'app_title': 'क्लोथिंग ईआरपी',
      'scan_barcode': 'बारकोड स्कैन करें',
      'offline_banner': 'ऑफ़लाइन मोड: परिवर्तन स्वतः सिंक होंगे।',
      'syncing': 'डेटा सिंक हो रहा है...',
      'session_expired': 'सत्र समाप्त हो गया। कृपया पुनः लॉगिन करें।',
      'conflict_alert': 'सिंक विवाद: सर्वर पर रिकॉर्ड बदल दिया गया है।',
      'discard': 'रद्द करें',
      'retry': 'पुनः प्रयास करें',
    },
    'mr': {
      'app_title': 'क्लोदिंग ईआरपी',
      'scan_barcode': 'बारकोड स्कॅन करा',
      'offline_banner': 'ऑफलाइन मोड: बदल आपोआप सिंक होतील.',
      'syncing': 'डेटा सिंक होत आहे...',
      'session_expired': 'सत्र संपले. कृपया पुन्हा लॉगिन करा.',
      'conflict_alert': 'सिंक संघर्ष: सर्व्हरवर रेकॉर्ड बदलले आहे.',
      'discard': 'रद्द करा',
      'retry': 'पुन्हा प्रयत्न करा',
    },
    'ta': {
      'app_title': 'ஆடை ஈஆர்பி',
      'scan_barcode': 'பார்கோடை ஸ்கேன் செய்க',
      'offline_banner': 'ஆஃப்லைன் பயன்முறை: மாற்றங்கள் தானாக ஒத்திசைக்கப்படும்.',
      'syncing': 'தரவு ஒத்திசைக்கப்படுகிறது...',
      'session_expired': 'அமர்வு காலாவதியானது. மீண்டும் உள்நுழையவும்.',
      'conflict_alert': 'ஒத்திசைவு முரண்பாடு: சேவையகத்தில் பதிவு மாற்றப்பட்டது.',
      'discard': 'நிராகரி',
      'retry': 'மீண்டும் முயற்சி செய்க',
    },
    'bn': {
      'app_title': 'ক্লোথিং ইআরপি',
      'scan_barcode': 'বারকোড স্ক্যান করুন',
      'offline_banner': 'অফলাইন মোড: পরিবর্তনগুলি স্বয়ংক্রিয়ভাবে সিঙ্ক হবে।',
      'syncing': 'ডেটা সিঙ্ক হচ্ছে...',
      'session_expired': 'সেশন শেষ হয়েছে। অনুগ্রহ করে পুনরায় লগইন করুন।',
      'conflict_alert': 'সিঙ্ক বিরোধ: সার্ভারে রেকর্ড পরিবর্তিত হয়েছে।',
      'discard': 'বাতিল করুন',
      'retry': 'পুনরায় চেষ্টা করুন',
    },
  };

  static String translate(String key, {String languageCode = 'en'}) {
    final langMap = _translations[languageCode] ?? _translations['en']!;
    return langMap[key] ?? key;
  }
}

export type LanguageCode =
  | 'en'
  | 'hi'
  | 'bn'
  | 'te'
  | 'mr'
  | 'ta'
  | 'gu'
  | 'kn'
  | 'ml'
  | 'pa'
  | 'or'
  | 'as'
  | 'ur';

export const languageOptions: Array<{ code: LanguageCode; label: string }> = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी (Hindi)' },
  { code: 'bn', label: 'বাংলা (Bengali)' },
  { code: 'te', label: 'తెలుగు (Telugu)' },
  { code: 'mr', label: 'मराठी (Marathi)' },
  { code: 'ta', label: 'தமிழ் (Tamil)' },
  { code: 'gu', label: 'ગુજરાતી (Gujarati)' },
  { code: 'kn', label: 'ಕನ್ನಡ (Kannada)' },
  { code: 'ml', label: 'മലയാളം (Malayalam)' },
  { code: 'pa', label: 'ਪੰਜਾਬੀ (Punjabi)' },
  { code: 'or', label: 'ଓଡ଼ିଆ (Odia)' },
  { code: 'as', label: 'অসমীয়া (Assamese)' },
  { code: 'ur', label: 'اردو (Urdu)' },
];

const english = {
  menu: 'Menu',
  officer: 'Officer',
  consumer: 'Consumer',
  dashboard: 'Dashboard',
  scanProduct: 'Scan Product',
  scanHistory: 'Scan History',
  complaints: 'Complaints',
  analytics: 'Analytics',
  violationMap: 'Violation Map',
  reports: 'Reports',
  profile: 'Profile',
  settings: 'Settings',
  logout: 'Logout',
  closeMenu: 'Close menu',
  openMenu: 'Open menu',
  searchPlaceholder: 'Search products, scans, complaints…',
  settingsSubtitle: 'Manage your preferences and account options.',
  account: 'Account',
  notifications: 'Notifications',
  pushNotifications: 'Push notifications',
  pushNotificationsDesc: 'Receive alerts on this device',
  scanAlerts: 'Scan result alerts',
  scanAlertsDesc: 'Notify when a scan completes',
  complaintAlerts: 'Complaint updates',
  complaintAlertsDesc: 'Notify on complaint status changes',
  preferences: 'Preferences',
  language: 'Language',
  darkMode: 'Dark mode',
  darkModeDesc: 'Use a darker theme across the application',
  security: 'Security',
  changePassword: 'Change password',
  twoFactor: 'Two-factor authentication',
  deleteAccount: 'Delete account',
  saveChanges: 'Save Changes',
  changesSaved: 'Settings applied successfully.',
};

export type TranslationKey = keyof typeof english;

const translations: Partial<Record<LanguageCode, Partial<Record<TranslationKey, string>>>> = {
  hi: {
    menu: 'मेनू', officer: 'अधिकारी', consumer: 'उपभोक्ता', dashboard: 'डैशबोर्ड', scanProduct: 'उत्पाद स्कैन करें', scanHistory: 'स्कैन इतिहास', complaints: 'शिकायतें', analytics: 'विश्लेषण', violationMap: 'उल्लंघन मानचित्र', reports: 'रिपोर्ट', profile: 'प्रोफ़ाइल', settings: 'सेटिंग्स', logout: 'लॉग आउट', closeMenu: 'मेनू बंद करें', openMenu: 'मेनू खोलें', searchPlaceholder: 'उत्पाद, स्कैन, शिकायतें खोजें…', settingsSubtitle: 'अपनी प्राथमिकताएँ और खाते के विकल्प प्रबंधित करें।', account: 'खाता', notifications: 'सूचनाएँ', pushNotifications: 'पुश सूचनाएँ', pushNotificationsDesc: 'इस डिवाइस पर अलर्ट प्राप्त करें', scanAlerts: 'स्कैन परिणाम अलर्ट', scanAlertsDesc: 'स्कैन पूरा होने पर सूचित करें', complaintAlerts: 'शिकायत अपडेट', complaintAlertsDesc: 'शिकायत की स्थिति बदलने पर सूचित करें', preferences: 'प्राथमिकताएँ', language: 'भाषा', darkMode: 'डार्क मोड', darkModeDesc: 'पूरे ऐप में गहरी थीम का उपयोग करें', security: 'सुरक्षा', changePassword: 'पासवर्ड बदलें', twoFactor: 'दो-स्तरीय प्रमाणीकरण', deleteAccount: 'खाता हटाएँ', saveChanges: 'परिवर्तन सहेजें', changesSaved: 'सेटिंग्स सफलतापूर्वक लागू हुईं।',
  },
  bn: {
    menu: 'মেনু', officer: 'কর্মকর্তা', consumer: 'ভোক্তা', dashboard: 'ড্যাশবোর্ড', scanProduct: 'পণ্য স্ক্যান', scanHistory: 'স্ক্যান ইতিহাস', complaints: 'অভিযোগ', analytics: 'বিশ্লেষণ', violationMap: 'লঙ্ঘন মানচিত্র', reports: 'রিপোর্ট', profile: 'প্রোফাইল', settings: 'সেটিংস', logout: 'লগ আউট', closeMenu: 'মেনু বন্ধ করুন', openMenu: 'মেনু খুলুন', searchPlaceholder: 'পণ্য, স্ক্যান, অভিযোগ খুঁজুন…', settingsSubtitle: 'আপনার পছন্দ ও অ্যাকাউন্টের বিকল্প পরিচালনা করুন।', account: 'অ্যাকাউন্ট', notifications: 'বিজ্ঞপ্তি', pushNotifications: 'পুশ বিজ্ঞপ্তি', pushNotificationsDesc: 'এই ডিভাইসে সতর্কতা পান', scanAlerts: 'স্ক্যান ফলাফলের সতর্কতা', scanAlertsDesc: 'স্ক্যান শেষ হলে জানান', complaintAlerts: 'অভিযোগ আপডেট', complaintAlertsDesc: 'অভিযোগের অবস্থা বদলালে জানান', preferences: 'পছন্দ', language: 'ভাষা', darkMode: 'ডার্ক মোড', darkModeDesc: 'অ্যাপ জুড়ে গাঢ় থিম ব্যবহার করুন', security: 'নিরাপত্তা', changePassword: 'পাসওয়ার্ড পরিবর্তন', twoFactor: 'দুই-ধাপের প্রমাণীকরণ', deleteAccount: 'অ্যাকাউন্ট মুছুন', saveChanges: 'পরিবর্তন সংরক্ষণ', changesSaved: 'সেটিংস সফলভাবে প্রয়োগ হয়েছে।',
  },
  te: {
    menu: 'మెను', officer: 'అధికారి', consumer: 'వినియోగదారు', dashboard: 'డ్యాష్‌బోర్డ్', scanProduct: 'ఉత్పత్తిని స్కాన్ చేయండి', scanHistory: 'స్కాన్ చరిత్ర', complaints: 'ఫిర్యాదులు', analytics: 'విశ్లేషణ', violationMap: 'ఉల్లంఘన మ్యాప్', reports: 'నివేదికలు', profile: 'ప్రొఫైల్', settings: 'సెట్టింగ్‌లు', logout: 'లాగ్ అవుట్', closeMenu: 'మెనును మూసివేయండి', openMenu: 'మెనును తెరవండి', searchPlaceholder: 'ఉత్పత్తులు, స్కాన్‌లు, ఫిర్యాదులను వెతకండి…', settingsSubtitle: 'మీ ప్రాధాన్యతలు మరియు ఖాతా ఎంపికలను నిర్వహించండి.', account: 'ఖాతా', notifications: 'నోటిఫికేషన్‌లు', pushNotifications: 'పుష్ నోటిఫికేషన్‌లు', pushNotificationsDesc: 'ఈ పరికరంలో అలర్ట్‌లను పొందండి', scanAlerts: 'స్కాన్ ఫలితాల అలర్ట్‌లు', scanAlertsDesc: 'స్కాన్ పూర్తయినప్పుడు తెలియజేయండి', complaintAlerts: 'ఫిర్యాదు నవీకరణలు', complaintAlertsDesc: 'ఫిర్యాదు స్థితి మారినప్పుడు తెలియజేయండి', preferences: 'ప్రాధాన్యతలు', language: 'భాష', darkMode: 'డార్క్ మోడ్', darkModeDesc: 'యాప్ అంతటా ముదురు థీమ్‌ను ఉపయోగించండి', security: 'భద్రత', changePassword: 'పాస్‌వర్డ్ మార్చండి', twoFactor: 'రెండు-దశల ధృవీకరణ', deleteAccount: 'ఖాతాను తొలగించండి', saveChanges: 'మార్పులను సేవ్ చేయండి', changesSaved: 'సెట్టింగ్‌లు విజయవంతంగా వర్తించాయి.',
  },
  mr: {
    menu: 'मेनू', officer: 'अधिकारी', consumer: 'ग्राहक', dashboard: 'डॅशबोर्ड', scanProduct: 'उत्पादन स्कॅन करा', scanHistory: 'स्कॅन इतिहास', complaints: 'तक्रारी', analytics: 'विश्लेषण', violationMap: 'उल्लंघन नकाशा', reports: 'अहवाल', profile: 'प्रोफाइल', settings: 'सेटिंग्ज', logout: 'लॉग आउट', closeMenu: 'मेनू बंद करा', openMenu: 'मेनू उघडा', searchPlaceholder: 'उत्पादने, स्कॅन, तक्रारी शोधा…', settingsSubtitle: 'तुमची प्राधान्ये आणि खाते पर्याय व्यवस्थापित करा.', account: 'खाते', notifications: 'सूचना', pushNotifications: 'पुश सूचना', pushNotificationsDesc: 'या डिव्हाइसवर अलर्ट मिळवा', scanAlerts: 'स्कॅन निकाल सूचना', scanAlertsDesc: 'स्कॅन पूर्ण झाल्यावर कळवा', complaintAlerts: 'तक्रार अद्यतने', complaintAlertsDesc: 'तक्रारीची स्थिती बदलल्यावर कळवा', preferences: 'प्राधान्ये', language: 'भाषा', darkMode: 'डार्क मोड', darkModeDesc: 'संपूर्ण अॅपमध्ये गडद थीम वापरा', security: 'सुरक्षा', changePassword: 'पासवर्ड बदला', twoFactor: 'द्वि-घटक प्रमाणीकरण', deleteAccount: 'खाते हटवा', saveChanges: 'बदल जतन करा', changesSaved: 'सेटिंग्ज यशस्वीरित्या लागू झाली.',
  },
  ta: {
    menu: 'மெனு', officer: 'அதிகாரி', consumer: 'நுகர்வோர்', dashboard: 'டாஷ்போர்டு', scanProduct: 'தயாரிப்பை ஸ்கேன் செய்க', scanHistory: 'ஸ்கேன் வரலாறு', complaints: 'புகார்கள்', analytics: 'பகுப்பாய்வு', violationMap: 'மீறல் வரைபடம்', reports: 'அறிக்கைகள்', profile: 'சுயவிவரம்', settings: 'அமைப்புகள்', logout: 'வெளியேறு', closeMenu: 'மெனுவை மூடு', openMenu: 'மெனுவைத் திற', searchPlaceholder: 'தயாரிப்புகள், ஸ்கேன்கள், புகார்களைத் தேடுங்கள்…', settingsSubtitle: 'உங்கள் விருப்பங்களையும் கணக்கு விருப்பங்களையும் நிர்வகிக்கவும்.', account: 'கணக்கு', notifications: 'அறிவிப்புகள்', pushNotifications: 'புஷ் அறிவிப்புகள்', pushNotificationsDesc: 'இந்த சாதனத்தில் எச்சரிக்கைகளைப் பெறுங்கள்', scanAlerts: 'ஸ்கேன் முடிவு எச்சரிக்கைகள்', scanAlertsDesc: 'ஸ்கேன் முடிந்ததும் அறிவிக்கவும்', complaintAlerts: 'புகார் புதுப்பிப்புகள்', complaintAlertsDesc: 'புகார் நிலை மாறும்போது அறிவிக்கவும்', preferences: 'விருப்பங்கள்', language: 'மொழி', darkMode: 'டார்க் மோட்', darkModeDesc: 'ஆப் முழுவதும் இருண்ட தீமைப் பயன்படுத்தவும்', security: 'பாதுகாப்பு', changePassword: 'கடவுச்சொல்லை மாற்றவும்', twoFactor: 'இரு-படி அங்கீகாரம்', deleteAccount: 'கணக்கை நீக்கு', saveChanges: 'மாற்றங்களைச் சேமி', changesSaved: 'அமைப்புகள் வெற்றிகரமாகப் பயன்படுத்தப்பட்டன.',
  },
  gu: {
    menu: 'મેનુ', officer: 'અધિકારી', consumer: 'ગ્રાહક', dashboard: 'ડેશબોર્ડ', scanProduct: 'ઉત્પાદન સ્કેન કરો', scanHistory: 'સ્કેન ઇતિહાસ', complaints: 'ફરિયાદો', analytics: 'વિશ્લેષણ', violationMap: 'ઉલ્લંઘન નકશો', reports: 'અહેવાલો', profile: 'પ્રોફાઇલ', settings: 'સેટિંગ્સ', logout: 'લૉગ આઉટ', closeMenu: 'મેનુ બંધ કરો', openMenu: 'મેનુ ખોલો', searchPlaceholder: 'ઉત્પાદનો, સ્કેન, ફરિયાદો શોધો…', settingsSubtitle: 'તમારી પસંદગીઓ અને એકાઉન્ટ વિકલ્પોનું સંચાલન કરો.', account: 'એકાઉન્ટ', notifications: 'સૂચનાઓ', pushNotifications: 'પુશ સૂચનાઓ', pushNotificationsDesc: 'આ ઉપકરણ પર ચેતવણીઓ મેળવો', scanAlerts: 'સ્કેન પરિણામ ચેતવણીઓ', scanAlertsDesc: 'સ્કેન પૂર્ણ થાય ત્યારે સૂચિત કરો', complaintAlerts: 'ફરિયાદ અપડેટ્સ', complaintAlertsDesc: 'ફરિયાદની સ્થિતિ બદલાય ત્યારે સૂચિત કરો', preferences: 'પસંદગીઓ', language: 'ભાષા', darkMode: 'ડાર્ક મોડ', darkModeDesc: 'આખી એપમાં ઘેરી થીમ વાપરો', security: 'સુરક્ષા', changePassword: 'પાસવર્ડ બદલો', twoFactor: 'બે-પગલાંનું પ્રમાણીકરણ', deleteAccount: 'એકાઉન્ટ કાઢી નાખો', saveChanges: 'ફેરફારો સાચવો', changesSaved: 'સેટિંગ્સ સફળતાપૂર્વક લાગુ થઈ.',
  },
  kn: {
    menu: 'ಮೆನು', officer: 'ಅಧಿಕಾರಿ', consumer: 'ಗ್ರಾಹಕ', dashboard: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', scanProduct: 'ಉತ್ಪನ್ನ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ', scanHistory: 'ಸ್ಕ್ಯಾನ್ ಇತಿಹಾಸ', complaints: 'ದೂರುಗಳು', analytics: 'ವಿಶ್ಲೇಷಣೆ', violationMap: 'ಉಲ್ಲಂಘನೆ ನಕ್ಷೆ', reports: 'ವರದಿಗಳು', profile: 'ಪ್ರೊಫೈಲ್', settings: 'ಸೆಟ್ಟಿಂಗ್‌ಗಳು', logout: 'ಲಾಗ್ ಔಟ್', closeMenu: 'ಮೆನು ಮುಚ್ಚಿ', openMenu: 'ಮೆನು ತೆರೆಯಿರಿ', searchPlaceholder: 'ಉತ್ಪನ್ನಗಳು, ಸ್ಕ್ಯಾನ್‌ಗಳು, ದೂರುಗಳನ್ನು ಹುಡುಕಿ…', settingsSubtitle: 'ನಿಮ್ಮ ಆದ್ಯತೆಗಳು ಮತ್ತು ಖಾತೆ ಆಯ್ಕೆಗಳನ್ನು ನಿರ್ವಹಿಸಿ.', account: 'ಖಾತೆ', notifications: 'ಅಧಿಸೂಚನೆಗಳು', pushNotifications: 'ಪುಶ್ ಅಧಿಸೂಚನೆಗಳು', pushNotificationsDesc: 'ಈ ಸಾಧನದಲ್ಲಿ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಪಡೆಯಿರಿ', scanAlerts: 'ಸ್ಕ್ಯಾನ್ ಫಲಿತಾಂಶದ ಎಚ್ಚರಿಕೆಗಳು', scanAlertsDesc: 'ಸ್ಕ್ಯಾನ್ ಪೂರ್ಣಗೊಂಡಾಗ ತಿಳಿಸಿ', complaintAlerts: 'ದೂರು ನವೀಕರಣಗಳು', complaintAlertsDesc: 'ದೂರು ಸ್ಥಿತಿ ಬದಲಾದಾಗ ತಿಳಿಸಿ', preferences: 'ಆದ್ಯತೆಗಳು', language: 'ಭಾಷೆ', darkMode: 'ಡಾರ್ಕ್ ಮೋಡ್', darkModeDesc: 'ಅಪ್ಲಿಕೇಶನ್‌ನಾದ್ಯಂತ ಗಾಢ ಥೀಮ್ ಬಳಸಿ', security: 'ಭದ್ರತೆ', changePassword: 'ಪಾಸ್‌ವರ್ಡ್ ಬದಲಾಯಿಸಿ', twoFactor: 'ಎರಡು ಹಂತದ ದೃಢೀಕರಣ', deleteAccount: 'ಖಾತೆ ಅಳಿಸಿ', saveChanges: 'ಬದಲಾವಣೆಗಳನ್ನು ಉಳಿಸಿ', changesSaved: 'ಸೆಟ್ಟಿಂಗ್‌ಗಳನ್ನು ಯಶಸ್ವಿಯಾಗಿ ಅನ್ವಯಿಸಲಾಗಿದೆ.',
  },
  ml: {
    menu: 'മെനു', officer: 'ഉദ്യോഗസ്ഥൻ', consumer: 'ഉപഭോക്താവ്', dashboard: 'ഡാഷ്ബോർഡ്', scanProduct: 'ഉൽപ്പന്നം സ്കാൻ ചെയ്യുക', scanHistory: 'സ്കാൻ ചരിത്രം', complaints: 'പരാതികൾ', analytics: 'വിശകലനം', violationMap: 'ലംഘന മാപ്പ്', reports: 'റിപ്പോർട്ടുകൾ', profile: 'പ്രൊഫൈൽ', settings: 'ക്രമീകരണങ്ങൾ', logout: 'ലോഗ് ഔട്ട്', closeMenu: 'മെനു അടയ്ക്കുക', openMenu: 'മെനു തുറക്കുക', searchPlaceholder: 'ഉൽപ്പന്നങ്ങൾ, സ്കാനുകൾ, പരാതികൾ തിരയുക…', settingsSubtitle: 'നിങ്ങളുടെ മുൻഗണനകളും അക്കൗണ്ട് ഓപ്ഷനുകളും നിയന്ത്രിക്കുക.', account: 'അക്കൗണ്ട്', notifications: 'അറിയിപ്പുകൾ', pushNotifications: 'പുഷ് അറിയിപ്പുകൾ', pushNotificationsDesc: 'ഈ ഉപകരണത്തിൽ അലേർട്ടുകൾ സ്വീകരിക്കുക', scanAlerts: 'സ്കാൻ ഫല അലേർട്ടുകൾ', scanAlertsDesc: 'സ്കാൻ പൂർത്തിയാകുമ്പോൾ അറിയിക്കുക', complaintAlerts: 'പരാതി അപ്‌ഡേറ്റുകൾ', complaintAlertsDesc: 'പരാതിയുടെ നില മാറുമ്പോൾ അറിയിക്കുക', preferences: 'മുൻഗണനകൾ', language: 'ഭാഷ', darkMode: 'ഡാർക്ക് മോഡ്', darkModeDesc: 'ആപ്പിലുടനീളം ഇരുണ്ട തീം ഉപയോഗിക്കുക', security: 'സുരക്ഷ', changePassword: 'പാസ്‌വേഡ് മാറ്റുക', twoFactor: 'രണ്ട് ഘട്ട പ്രാമാണീകരണം', deleteAccount: 'അക്കൗണ്ട് ഇല്ലാതാക്കുക', saveChanges: 'മാറ്റങ്ങൾ സംരക്ഷിക്കുക', changesSaved: 'ക്രമീകരണങ്ങൾ വിജയകരമായി പ്രയോഗിച്ചു.',
  },
  pa: {
    menu: 'ਮੀਨੂ', officer: 'ਅਧਿਕਾਰੀ', consumer: 'ਖਪਤਕਾਰ', dashboard: 'ਡੈਸ਼ਬੋਰਡ', scanProduct: 'ਉਤਪਾਦ ਸਕੈਨ ਕਰੋ', scanHistory: 'ਸਕੈਨ ਇਤਿਹਾਸ', complaints: 'ਸ਼ਿਕਾਇਤਾਂ', analytics: 'ਵਿਸ਼ਲੇਸ਼ਣ', violationMap: 'ਉਲੰਘਣਾ ਨਕਸ਼ਾ', reports: 'ਰਿਪੋਰਟਾਂ', profile: 'ਪ੍ਰੋਫਾਈਲ', settings: 'ਸੈਟਿੰਗਾਂ', logout: 'ਲੌਗ ਆਊਟ', closeMenu: 'ਮੀਨੂ ਬੰਦ ਕਰੋ', openMenu: 'ਮੀਨੂ ਖੋਲ੍ਹੋ', searchPlaceholder: 'ਉਤਪਾਦ, ਸਕੈਨ ਅਤੇ ਸ਼ਿਕਾਇਤਾਂ ਖੋਜੋ…', settingsSubtitle: 'ਆਪਣੀਆਂ ਤਰਜੀਹਾਂ ਅਤੇ ਖਾਤੇ ਦੇ ਵਿਕਲਪਾਂ ਦਾ ਪ੍ਰਬੰਧ ਕਰੋ।', account: 'ਖਾਤਾ', notifications: 'ਸੂਚਨਾਵਾਂ', pushNotifications: 'ਪੁਸ਼ ਸੂਚਨਾਵਾਂ', pushNotificationsDesc: 'ਇਸ ਡਿਵਾਈਸ ਤੇ ਚੇਤਾਵਨੀਆਂ ਪ੍ਰਾਪਤ ਕਰੋ', scanAlerts: 'ਸਕੈਨ ਨਤੀਜਾ ਚੇਤਾਵਨੀਆਂ', scanAlertsDesc: 'ਸਕੈਨ ਪੂਰਾ ਹੋਣ ਤੇ ਸੂਚਿਤ ਕਰੋ', complaintAlerts: 'ਸ਼ਿਕਾਇਤ ਅੱਪਡੇਟ', complaintAlertsDesc: 'ਸ਼ਿਕਾਇਤ ਦੀ ਸਥਿਤੀ ਬਦਲਣ ਤੇ ਸੂਚਿਤ ਕਰੋ', preferences: 'ਤਰਜੀਹਾਂ', language: 'ਭਾਸ਼ਾ', darkMode: 'ਡਾਰਕ ਮੋਡ', darkModeDesc: 'ਪੂਰੀ ਐਪ ਵਿੱਚ ਗੂੜ੍ਹੀ ਥੀਮ ਵਰਤੋ', security: 'ਸੁਰੱਖਿਆ', changePassword: 'ਪਾਸਵਰਡ ਬਦਲੋ', twoFactor: 'ਦੋ-ਕਦਮ ਪ੍ਰਮਾਣੀਕਰਨ', deleteAccount: 'ਖਾਤਾ ਮਿਟਾਓ', saveChanges: 'ਤਬਦੀਲੀਆਂ ਸੁਰੱਖਿਅਤ ਕਰੋ', changesSaved: 'ਸੈਟਿੰਗਾਂ ਸਫਲਤਾਪੂਰਵਕ ਲਾਗੂ ਹੋਈਆਂ।',
  },
  or: {
    menu: 'ମେନୁ', officer: 'ଅଧିକାରୀ', consumer: 'ଗ୍ରାହକ', dashboard: 'ଡ୍ୟାସବୋର୍ଡ', scanProduct: 'ଉତ୍ପାଦ ସ୍କାନ୍ କରନ୍ତୁ', scanHistory: 'ସ୍କାନ୍ ଇତିହାସ', complaints: 'ଅଭିଯୋଗ', analytics: 'ବିଶ୍ଳେଷଣ', violationMap: 'ଉଲ୍ଲଂଘନ ମାନଚିତ୍ର', reports: 'ରିପୋର୍ଟ', profile: 'ପ୍ରୋଫାଇଲ୍', settings: 'ସେଟିଂସ୍', logout: 'ଲଗ୍ ଆଉଟ୍', closeMenu: 'ମେନୁ ବନ୍ଦ କରନ୍ତୁ', openMenu: 'ମେନୁ ଖୋଲନ୍ତୁ', searchPlaceholder: 'ଉତ୍ପାଦ, ସ୍କାନ୍, ଅଭିଯୋଗ ଖୋଜନ୍ତୁ…', settingsSubtitle: 'ଆପଣଙ୍କ ପସନ୍ଦ ଏବଂ ଆକାଉଣ୍ଟ ବିକଳ୍ପ ପରିଚାଳନା କରନ୍ତୁ।', account: 'ଆକାଉଣ୍ଟ', notifications: 'ବିଜ୍ଞପ୍ତି', pushNotifications: 'ପୁସ୍ ବିଜ୍ଞପ୍ତି', pushNotificationsDesc: 'ଏହି ଡିଭାଇସରେ ସତର୍କତା ପାଆନ୍ତୁ', scanAlerts: 'ସ୍କାନ୍ ଫଳାଫଳ ସତର୍କତା', scanAlertsDesc: 'ସ୍କାନ୍ ସମାପ୍ତ ହେଲେ ଜଣାନ୍ତୁ', complaintAlerts: 'ଅଭିଯୋଗ ଅପଡେଟ୍', complaintAlertsDesc: 'ଅଭିଯୋଗ ସ୍ଥିତି ବଦଳିଲେ ଜଣାନ୍ତୁ', preferences: 'ପସନ୍ଦ', language: 'ଭାଷା', darkMode: 'ଡାର୍କ ମୋଡ୍', darkModeDesc: 'ସମଗ୍ର ଆପରେ ଗାଢ଼ ଥିମ୍ ବ୍ୟବହାର କରନ୍ତୁ', security: 'ସୁରକ୍ଷା', changePassword: 'ପାସୱାର୍ଡ ବଦଳାନ୍ତୁ', twoFactor: 'ଦୁଇ-ପଦକ୍ଷେପ ପ୍ରମାଣୀକରଣ', deleteAccount: 'ଆକାଉଣ୍ଟ ଡିଲିଟ୍ କରନ୍ତୁ', saveChanges: 'ପରିବର୍ତ୍ତନ ସଞ୍ଚୟ କରନ୍ତୁ', changesSaved: 'ସେଟିଂସ୍ ସଫଳତାର ସହ ପ୍ରୟୋଗ ହୋଇଛି।',
  },
  as: {
    menu: 'মেনু', officer: 'কৰ্মকৰ্তা', consumer: 'গ্ৰাহক', dashboard: 'ডেশ্বব’ৰ্ড', scanProduct: 'সামগ্ৰী স্কেন কৰক', scanHistory: 'স্কেন ইতিহাস', complaints: 'অভিযোগ', analytics: 'বিশ্লেষণ', violationMap: 'উলংঘন মানচিত্ৰ', reports: 'প্ৰতিবেদন', profile: 'প্ৰ’ফাইল', settings: 'ছেটিংছ', logout: 'লগ আউট', closeMenu: 'মেনু বন্ধ কৰক', openMenu: 'মেনু খোলক', searchPlaceholder: 'সামগ্ৰী, স্কেন, অভিযোগ বিচাৰক…', settingsSubtitle: 'আপোনাৰ পছন্দ আৰু একাউণ্টৰ বিকল্পসমূহ পৰিচালনা কৰক।', account: 'একাউণ্ট', notifications: 'জাননী', pushNotifications: 'পুছ জাননী', pushNotificationsDesc: 'এই ডিভাইচত সতৰ্কবাৰ্তা লাভ কৰক', scanAlerts: 'স্কেন ফলাফলৰ সতৰ্কবাৰ্তা', scanAlertsDesc: 'স্কেন সম্পূৰ্ণ হ’লে জনাওক', complaintAlerts: 'অভিযোগ আপডেট', complaintAlertsDesc: 'অভিযোগৰ স্থিতি সলনি হ’লে জনাওক', preferences: 'পছন্দসমূহ', language: 'ভাষা', darkMode: 'ডাৰ্ক মোড', darkModeDesc: 'সমগ্ৰ এপত গাঢ় থীম ব্যৱহাৰ কৰক', security: 'সুৰক্ষা', changePassword: 'পাছৱৰ্ড সলনি কৰক', twoFactor: 'দুটা স্তৰৰ প্ৰমাণীকৰণ', deleteAccount: 'একাউণ্ট মচক', saveChanges: 'পৰিবৰ্তন সংৰক্ষণ কৰক', changesSaved: 'ছেটিংছ সফলভাৱে প্ৰয়োগ কৰা হ’ল।',
  },
  ur: {
    menu: 'مینو', officer: 'افسر', consumer: 'صارف', dashboard: 'ڈیش بورڈ', scanProduct: 'مصنوعات اسکین کریں', scanHistory: 'اسکین کی تاریخ', complaints: 'شکایات', analytics: 'تجزیات', violationMap: 'خلاف ورزی کا نقشہ', reports: 'رپورٹس', profile: 'پروفائل', settings: 'ترتیبات', logout: 'لاگ آؤٹ', closeMenu: 'مینو بند کریں', openMenu: 'مینو کھولیں', searchPlaceholder: 'مصنوعات، اسکین اور شکایات تلاش کریں…', settingsSubtitle: 'اپنی ترجیحات اور اکاؤنٹ کے اختیارات کا انتظام کریں۔', account: 'اکاؤنٹ', notifications: 'اطلاعات', pushNotifications: 'پش اطلاعات', pushNotificationsDesc: 'اس ڈیوائس پر انتباہات حاصل کریں', scanAlerts: 'اسکین کے نتائج کی اطلاعات', scanAlertsDesc: 'اسکین مکمل ہونے پر اطلاع دیں', complaintAlerts: 'شکایت کی تازہ کاری', complaintAlertsDesc: 'شکایت کی حالت بدلنے پر اطلاع دیں', preferences: 'ترجیحات', language: 'زبان', darkMode: 'ڈارک موڈ', darkModeDesc: 'پوری ایپ میں گہری تھیم استعمال کریں', security: 'سیکیورٹی', changePassword: 'پاس ورڈ تبدیل کریں', twoFactor: 'دو مرحلہ تصدیق', deleteAccount: 'اکاؤنٹ حذف کریں', saveChanges: 'تبدیلیاں محفوظ کریں', changesSaved: 'ترتیبات کامیابی سے لاگو ہو گئیں۔',
  },
};

export function translate(language: LanguageCode, key: TranslationKey): string {
  return translations[language]?.[key] || english[key];
}

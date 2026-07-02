# Figma photo re-tag list (for Elise's tag plugin)

85 photos need their hidden tag layers corrected in the Figma file
to match the audited source of truth. Total 161 field edits.
ADAM already reads the corrected values via refs/photo_library_tags.csv;
this brings the Figma layers (the eventual source of truth) back in sync.

## coding_together_kv  (node 5063:1217)
  - device: 'desktop_monitor'  ->  'desktop_monitor, headphones, coffee'
  - description: 'Asian man at desktop in modern dev office smiling'  ->  'Asian man in cap and headphones at dual monitors smiling in office'

## coding_together_02  (node 5063:1219)
  - device: 'desktop_monitor'  ->  'desktop_monitor, headphones'
  - description: 'Asian man close at desktop monitor focused'  ->  'Asian man in cap, headphones on neck, focused at desktop monitor'

## coding_together_04  (node 5087:191)
  - description: 'Asian man with laptop in chair facing camera'  ->  'Asian man with laptop in lounge chair facing camera smiling'

## coding_together_01  (node 5063:1231)
  - device: 'desktop_monitor'  ->  'desktop_monitor, headphones'
  - description: 'Asian man at desktop with headphones video call visible'  ->  'Asian man in headphones on video call at desktop monitors'

## coding_together_07  (node 5063:1233)
  - people: 'hands_only'  ->  'man_1'
  - description: 'Tablet close-up on patterned floor hands view'  ->  'Man in cap holding tablet, profile view, on patterned rug'

## coding_together_05  (node 5063:1192)
  - description: 'Asian man sitting on patterned floor with tablet'  ->  'Asian man sitting on patterned rug using tablet'

## coding_together_06  (node 5063:1193)
  - description: 'Asian man sitting on floor holding phone'  ->  'Asian man sitting on rug holding phone with earbuds'

## coding_together_03  (node 5063:1232)
  - device: 'phone'  ->  'phone, coffee'
  - description: 'Hands close-up holding phone scrolling'  ->  'Hands holding phone at desk with keyboard and coffee mug'

## coding_together_09  (node 5063:1258)
  - description: 'Asian man in chair with phone in evening warm light'  ->  'Asian man in chair using phone in warm evening light'

## coding_together_10  (node 5063:1259)
  - description: 'Asian man in chair with laptop in lap smiling evening'  ->  'Asian man in chair with laptop in lap smiling in evening light'

## coding_together_13  (node 5063:1260)
  - people: 'hands_only'  ->  'man_1'
  - device: 'tablet'  ->  'phone'
  - description: 'Tablet view from above on patterned floor'  ->  'Man in cap viewing phone from above on patterned rug'

## coding_together_08  (node 5063:1272)
  - device: 'desktop_monitor, notebook'  ->  'desktop_monitor, notebook, headphones'
  - activity: 'writing'  ->  'working'
  - description: 'Asian man at desk with notebook and desktop monitor warm light'  ->  'Asian man at desk with monitor, notebook, headphones on neck'

## coding_together_11  (node 5063:1271)
  - device: 'headphones'  ->  'headphones, desktop_monitor'
  - activity: 'facing_camera'  ->  'working'
  - description: 'Asian man with headphones close-up looking right'  ->  'Asian man in headphones looking at monitor, warm evening office'

## coding_together_12  (node 5063:1270)
  - description: 'Asian man centered headshot with cap and headphones smiling'  ->  'Asian man in cap and headphones, hand on chin, smiling at camera'

## coding_together_14  (node 5063:1269)
  - description: 'Asian man holding tablet looking at it focused'  ->  'Asian man holding tablet reading, warm daylight office'

## coding_together_15  (node 5063:1268)
  - description: 'Asian man profile at desktop with headphones around neck evening'  ->  'Asian man in cap at desktop monitor, headphones around neck, evening'

## fashion_week_02  (node 5063:1197)
  - description: 'Same two together with tablet looking at it'  ->  'White woman in vest and Asian man holding tablet, looking at it'

## fashion_week_03  (node 5063:1199)
  - device: 'laptop'  ->  'laptop, coffee'

## fashion_week_kv  (node 5063:1234)
  - people: 'woman_1, woman_2, hands_only'  ->  'woman_1, man_2, hands_only'
  - demographic: 'white'  ->  'mixed'
  - device: 'laptop'  ->  'laptop, coffee'
  - description: 'Two women at laptop with hands of third person in foreground'  ->  'Asian man and woman in vest talk; third person types laptop w/ Upwork'

## fashion_week_06  (node 5063:1238)
  - activity: 'working'  ->  'typing'
  - description: 'Hands close-up on laptop showing Upwork interface'  ->  'Hands close-up typing on laptop showing Upwork interface'

## fashion_week_04  (node 5063:1201)
  - people: 'woman_2'  ->  'woman_1, woman_2'
  - age: 'mature'  ->  'mixed'
  - device: 'laptop'  ->  'desktop_monitor'
  - description: 'Mature white woman at laptop with woman in foreground back-to-camera'  ->  'Mature white woman using monitor; woman in vest foreground, back to camera'

## fashion_week_05  (node 5063:1237)
  - people: 'woman_2'  ->  'woman_2, man_2'
  - demographic: 'white'  ->  'mixed'
  - age: 'mature'  ->  'mixed'
  - activity: 'facing_camera'  ->  'listening'
  - description: 'Mature white woman close-up smiling at desk'  ->  'Mature white woman listening to man across desk, laptop in foreground'

## fashion_week_12  (node 5063:1261)
  - people: 'hands_only, woman_1'  ->  'woman_1, man_2, hands_only'
  - demographic: 'white'  ->  'mixed'
  - description: 'Hands at desktop monitor with woman in foreground'  ->  'Woman in vest at desktop monitor, man across desk, hands on calculator'

## fashion_week_07  (node 5063:1265)
  - device: 'none'  ->  'tablet, coffee'
  - activity: 'presenting'  ->  'meeting'
  - description: 'White woman in vest and Asian man with bun standing at whiteboard'  ->  'Asian man holding tablet and coffee showing white woman in vest'

## fashion_week_08  (node 5063:1264)
  - people: 'woman_2'  ->  'woman_1, woman_2, man_2'
  - demographic: 'white'  ->  'mixed'
  - age: 'mature'  ->  'mixed'
  - device: 'laptop'  ->  'laptop, desktop_monitor'

## fashion_week_10  (node 5063:1263)
  - device: 'laptop'  ->  'laptop, desktop_monitor'
  - style_fit: 'testimonial'  ->  'lifestyle_photo'
  - activity: 'facing_camera'  ->  'gesturing'
  - description: 'White woman in vest close-up at desk fashion sketches behind'  ->  'White woman in vest gesturing while talking at desk, sketches behind'

## fashion_week_11  (node 5063:1262)
  - description: 'White woman and Asian man with bun at laptop side angle'  ->  'White woman and Asian man with bun at laptop, side angle'

## fashion_week_09  (node 5063:1267)
  - description: 'White woman close-up portrait smiling testimonial'  ->  'White woman close-up portrait smiling, testimonial'

## finance_traveller_kv  (node 5063:1203)
  - device: 'laptop'  ->  'laptop, coffee'

## finance_traveller_04  (node 5063:1235)
  - device: 'laptop'  ->  'laptop, coffee'

## finance_traveller_05  (node 5063:1208)
  - device: 'laptop, coffee'  ->  'laptop, coffee, notebook'

## finance_traveller_06  (node 5063:1210)
  - device: 'laptop, coffee'  ->  'laptop, coffee, notebook'

## finance_traveler_08  (node 5063:1274)
  - device: 'laptop'  ->  'laptop, coffee, notebook'

## finance_traveler_09  (node 5063:1275)
  - device: 'phone, notebook'  ->  'phone, notebook, laptop'

## finance_traveler_12  (node 5063:1276)
  - device: 'tablet'  ->  'tablet, notebook, coffee'

## finance_traveler_14  (node 5063:1277)
  - device: 'coffee'  ->  'coffee, laptop'

## food_warehouse_02  (node 5063:1213)
  - device: 'tablet'  ->  'tablet, notebook'
  - activity: 'meeting'  ->  'gesturing'
  - description: 'Black woman with afro and Latino man with beard tablet warehouse'  ->  'Black woman with afro pointing and Latino man with tablet warehouse'

## food_warehouse_07  (node 5063:1239)
  - age: 'young_adult'  ->  'mixed'
  - device: 'laptop, tablet, phone'  ->  'laptop, tablet, coffee, notebook'
  - description: 'Hands close-up at desk with laptop tablet phone coffee'  ->  'Hands close-up at desk with laptop tablet coffee notebook'

## food_warehouse_03  (node 5063:1214)
  - device: 'notebook'  ->  'tablet'
  - description: 'Asian woman and Black woman with clipboard plus back-to-camera person'  ->  'Asian woman and Black woman with tablet plus back-to-camera person'

## food_warehouse_05  (node 5063:1216)
  - device: 'notebook'  ->  'tablet, notebook'
  - description: 'Latino man and Black woman looking at clipboard'  ->  'Latino man and Black woman reviewing a device together'

## food_warehouse_03b  (node 5063:1241)
  - device: 'laptop, notebook'  ->  'tablet'
  - description: 'Asian woman and Black woman with clipboard laptop visible'  ->  'Asian woman and Black woman with tablet showing screen'

## food_warehouse_11  (node 5063:1303)
  - device: 'laptop'  ->  'laptop, coffee'

## food_warehouse_10  (node 5063:1306)
  - device: 'tablet'  ->  'tablet, phone'

## food_warehouse_12  (node 5063:1305)
  - activity: 'facing_camera'  ->  'listening'

## food_warehouse_13  (node 5063:1309)
  - age: 'young_adult'  ->  'adult'
  - device: 'laptop'  ->  'laptop, tablet, coffee'
  - description: 'Asian woman Latino man and Black woman with laptop and packaging'  ->  'Asian woman Latino man and Black woman with laptop tablet and packaging'

## latenight_ai_04  (node 5063:1191)
  - description: 'White man with curly red hair on couch with laptop smiling'  ->  'White man with curly red hair on couch with laptop warm lamp'

## latenight_ai_kv  (node 5063:1242)
  - device: 'phone'  ->  'laptop, desktop_monitor'
  - style_fit: 'photo_with_text'  ->  'lifestyle_photo'
  - activity: 'on_phone'  ->  'working'
  - description: 'Hands close-up holding phone with desk setup behind'  ->  'Back view man at desk with laptop and monitor headphones'

## latenight_ai_05  (node 5063:1243)
  - device: 'laptop'  ->  'phone, desktop_monitor, headphones'
  - activity: 'working'  ->  'on_phone'
  - description: 'Hands at laptop showing Upwork with lamp'  ->  'Hands holding phone showing Upwork app at desk with keyboard'

## latenight_ai_06  (node 5063:1244)
  - people: 'man_4'  ->  'hands_only'
  - device: 'desktop_monitor, headphones'  ->  'laptop, headphones, desktop_monitor'
  - description: 'White man with curly red hair at desktop monitor profile'  ->  'Over-shoulder man using laptop showing Upwork headphones around neck'

## latenight_ai_07  (node 5063:1281)
  - device: 'laptop, desktop_monitor'  ->  'desktop_monitor, headphones'
  - description: 'White man with curly red hair at desk with laptop and monitors'  ->  'White man profile with headphones at monitor showing Upwork'

## latenight_ai_08  (node 5063:1282)
  - device: 'laptop'  ->  'laptop, desktop_monitor, headphones'
  - activity: 'browsing'  ->  'working'
  - description: 'White man with curly red hair on couch with laptop browsing'  ->  'White man on chair with laptop headphones monitor behind'

## latenight_ai_14  (node 5063:1286)
  - people: 'man_4'  ->  'hands_only'
  - device: 'laptop, desktop_monitor'  ->  'laptop, phone, headphones'
  - description: 'White man back at desk with laptop and monitors brick wall'  ->  'Back view man holding phone with laptop showing Upwork headphones'

## latenight_ai_09  (node 5063:1283)
  - people: 'man_4'  ->  'hands_only'
  - device: 'desktop_monitor, headphones'  ->  'laptop, desktop_monitor, headphones'
  - description: 'White man with headphones at desktop monitor back view'  ->  'Back view man at monitor showing code with laptop video call headphones'

## latenight_ai_11  (node 5063:1284)
  - device: 'headphones'  ->  'desktop_monitor, headphones'
  - style_fit: 'testimonial'  ->  'lifestyle_photo'

## latenight_ai_12  (node 5063:1285)
  - people: 'man_4'  ->  'hands_only'
  - description: 'White man back at full desk setup with two monitors and laptop'  ->  'Back view person at desk with laptop and monitor brick wall'

## latenight_ai_13  (node 5063:1287)
  - device: 'headphones'  ->  'desktop_monitor, headphones'

## latenight_ai_10  (node 5063:1288)
  - device: 'desktop_monitor'  ->  'desktop_monitor, headphones'
  - description: 'White man at desk typing with monitor warm lighting'  ->  'White man typing at desk with monitor and headphones'

## music_company_kv  (node 5063:1194)
  - device: 'headphones'  ->  'tablet, headphones, coffee'

## music_company_02  (node 5063:1196)
  - device: 'laptop'  ->  'laptop, tablet, headphones'
  - activity: 'meeting'  ->  'facing_camera'

## music_company_03  (node 5063:1198)
  - device: 'laptop'  ->  'laptop, headphones'

## music_company_01  (node 5063:1246)
  - device: 'laptop'  ->  'laptop, headphones'

## music_company_07  (node 5063:1245)
  - people: 'woman_6'  ->  'hands_only'
  - age: 'young_adult'  ->  'mixed'

## music_company_12  (node 5063:1289)
  - people: 'woman_6'  ->  'hands_only'
  - age: 'young_adult'  ->  'mixed'
  - activity: 'working'  ->  'typing'

## music_company_08  (node 5063:1290)
  - device: 'desktop_monitor'  ->  'desktop_monitor, headphones'

## music_company_10  (node 5063:1293)
  - device: 'desktop_monitor, coffee'  ->  'desktop_monitor, coffee, headphones'

## music_company_13  (node 5063:1291)
  - device: 'laptop'  ->  'tablet, laptop, headphones'
  - description: 'Both women at laptop with vinyl visible Black woman pointing'  ->  'White woman pointing at tablet with Black woman in studio'

## plant_supply_kv  (node 5063:1206)
  - people: 'man_4, woman_8'  ->  'man_4, woman_8, hands_only'
  - device: 'tablet'  ->  'tablet, notebook'

## plant_supply_01  (node 5063:1207)
  - people: 'man_4, woman_8'  ->  'man_4, woman_8, man_5'
  - device: 'tablet'  ->  'tablet, notebook'

## plant_supply_02  (node 5063:1247)
  - demographic: 'asian'  ->  'mixed'
  - device: 'laptop'  ->  'laptop, notebook'
  - activity: 'working'  ->  'typing'

## plant_supply_10  (node 5063:1296)
  - device: 'tablet'  ->  'tablet, notebook'

## plant_supply_12  (node 5063:1297)
  - device: 'phone'  ->  'phone, notebook'

## plant_supply_11  (node 5063:1299)
  - people: 'man_4, woman_8'  ->  'man_4, woman_8, man_5'

## plant_supply_13  (node 5063:1298)
  - device: 'laptop'  ->  'tablet'
  - description: 'White man with red hair at laptop and Asian woman gesturing'  ->  'White man with red hair at tablet and Asian woman gesturing'

## plant_supply_09  (node 5063:1300)
  - activity: 'gesturing'  ->  'waving'

## space_solutions_kv  (node 5063:1224)
  - device: 'desktop_monitor'  ->  'desktop_monitor, coffee, notebook'

## space_solutions_01  (node 5063:1225)
  - style_fit: 'testimonial'  ->  'lifestyle_photo'
  - description: 'Mature Black man with grey hair at desktop monitor close'  ->  'Mature Black man with grey hair at desk in dark office thinking'

## space_solutions_02  (node 5063:1226)
  - people: 'man_6'  ->  'man_6, hands_only'
  - device: 'tablet'  ->  'tablet, desktop_monitor, notebook'
  - description: 'Mature Black man at desktop with tablet handed to him'  ->  'Mature Black man at desk being handed a tablet by another person'

## space_solutions_06_r2  (node 5063:1249)
  - device: 'phone'  ->  'phone, desktop_monitor, notebook, headphones'
  - description: 'Hands holding phone close at desk with notebook'  ->  'Hands holding phone at desk with notebook monitor and earbuds'

## space_solutions_03  (node 5063:1227)
  - device: 'none'  ->  'desktop_monitor'

## space_solutions_04  (node 5063:1228)
  - device: 'phone'  ->  'desktop_monitor, notebook, headphones'
  - activity: 'on_phone'  ->  'facing_camera'
  - description: 'South Asian woman holding phone close at desktop'  ->  'South Asian woman smiling handing papers at desk'

## space_solutions_07  (node 5063:1250)
  - device: 'laptop'  ->  'laptop, phone'

## space_solutions_09  (node 5063:1313)
  - activity: 'working'  ->  'typing'
  - description: 'South Asian woman at desktop with notebook profile'  ->  'South Asian woman typing at desktop with notebook profile'

## space_solutions_12  (node 5063:1310)
  - device: 'tablet'  ->  'tablet, notebook'
  - description: 'Hands holding tablet showing Upwork data dark setting'  ->  'Hands holding tablet showing data with notebook on desk'

## space_solutions_08  (node 5063:1316)
  - demographic: 'mixed'  ->  'south_asian'

## space_solutions_10  (node 5063:1315)
  - device: 'none'  ->  'desktop_monitor'

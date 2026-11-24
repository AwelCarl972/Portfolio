// Extrait remis en forme de MultiFrame_SupportLine_Ichimoku (MQL5, 2022) : un même indicateur lu
// sur trois unités de temps, et une détection de nouvelle bougie pour ne pas
// recalculer à chaque tick.
#include <Trade\trade.mqh>
#include <Indicators\Trend.mqh>

CTrade      trade;
CiIchimoku *ichimokuTF1;
CiIchimoku *ichimokuTF2;
CiIchimoku *ichimokuTF3;

input ENUM_TIMEFRAMES TF1 = PERIOD_H1;    // tendance de fond
input ENUM_TIMEFRAMES TF2 = PERIOD_M15;   // confirmation
input ENUM_TIMEFRAMES TF3 = PERIOD_M5;    // déclenchement

void OnInit()
{
   ichimokuTF1 = new CiIchimoku();  ichimokuTF1.Create(_Symbol, TF1, 9, 26, 52);
   ichimokuTF2 = new CiIchimoku();  ichimokuTF2.Create(_Symbol, TF2, 9, 26, 52);
   ichimokuTF3 = new CiIchimoku();  ichimokuTF3.Create(_Symbol, TF3, 9, 26, 52);
}

void OnTick()
{
   // Taille de position proportionnelle au capital disponible
   double argentDispo = AccountInfoDouble(ACCOUNT_BALANCE);
   double Lot         = NormalizeDouble(argentDispo * 10 / 200000, 2);

   // Nouvelle bougie sur l'unité la plus fine : le reste du code ne tourne qu'une fois par bougie
   static datetime dtBarCurrent = WRONG_VALUE;
   datetime dtBarPrevious = dtBarCurrent;
   dtBarCurrent    = (datetime)SeriesInfoInteger(_Symbol, TF3, SERIES_LASTBAR_DATE);
   bool NewBarFlag = (dtBarCurrent != dtBarPrevious);

   // Nuage d'Ichimoku de l'unité de fond : le Senkou Span est projeté 26 périodes en avant
   ichimokuTF1.Refresh(-1);
   double SpanA_TF1 = ichimokuTF1.SenkouSpanA(-26);
   double SpanB_TF1 = ichimokuTF1.SenkouSpanB(-26);
   double Kijun_TF1 = ichimokuTF1.KijunSen(0);
   // … même lecture pour TF2 et TF3, puis tracé des niveaux A/B comme supports
}

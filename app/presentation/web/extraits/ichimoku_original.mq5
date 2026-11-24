// MultiFrame_SupportLine_Ichimoku : le code original, tel qu'écrit en 2022 (non retouché).
#include <Trade\trade.mqh>
#include <Indicators\Trend.mqh>
#include <Indicators\Indicator.mqh>
#include <Indicators\Indicators.mqh>
#include <Trade\PositionInfo.mqh>

CTrade trade;
CiIchimoku*ichimokuTF1;
CiIchimoku*ichimokuTF2;
CiIchimoku*ichimokuTF3;

double SKSpanANowValueTF1  =  EMPTY_VALUE;
double SKSpanBNowValueTF1  =  EMPTY_VALUE;
double SKSpanANowValueTF2  =  EMPTY_VALUE;
double SKSpanBNowValueTF2  =  EMPTY_VALUE;



/*--------------------------------Variables----------------------------------*/


input ENUM_TIMEFRAMES TF1  =  PERIOD_H1;     // Timeframe 1
input ENUM_TIMEFRAMES TF2  =  PERIOD_M15;     // Timeframe 2
input ENUM_TIMEFRAMES TF3  =  PERIOD_M5;    // Timeframe 3

input int SLValue =  100;
input int TPValue =  100;

void OnInit()
{
   ichimokuTF1 = new CiIchimoku();
   ichimokuTF1.Create(_Symbol,TF1,9,26,52);
   
   ichimokuTF2 = new CiIchimoku();
   ichimokuTF2.Create(_Symbol,TF2,9,26,52);
   
   ichimokuTF3 = new CiIchimoku();
   ichimokuTF3.Create(_Symbol,TF3,9,26,52);
   
   A_TF1Line();
   B_TF1Line();
   A_TF2Line();
   B_TF2Line();
   
}/*Fin OnInit*/

//-------------------------------------------------------------------------------

void OnTick()
{

/*--------------------------------Informations---------------------------------*/
   
   double argentDispo            =  AccountInfoDouble(ACCOUNT_BALANCE);
   double Ask                    =  NormalizeDouble(SymbolInfoDouble(_Symbol,SYMBOL_ASK),_Digits);
   double Bid                    =  NormalizeDouble(SymbolInfoDouble(_Symbol,SYMBOL_BID),_Digits);
   long   TypedePosition         =  PositionGetInteger(POSITION_TYPE);
   double EffetLevier            =  10;
   double LotBrut                =  (argentDispo*EffetLevier)/200000;
   double Lot                    =  NormalizeDouble(LotBrut,2);
   
   double OpenBarTF1             =  iOpen(_Symbol,TF1,0);
   double CloseBarTF1            =  iClose(_Symbol,TF1,1);
   
   double OpenBarTF2             =  iOpen(_Symbol,TF2,0);
   double CloseBarTF2            =  iClose(_Symbol,TF2,1);
   
   double OpenBarTF3             =  iOpen(_Symbol,TF3,0);
   double CloseBarTF3            =  iClose(_Symbol,TF3,1);
   
   static datetime dtBarCurrent  =  WRONG_VALUE;
   datetime dtBarPrevious        =  dtBarCurrent;
   dtBarCurrent                  =  (datetime)SeriesInfoInteger(_Symbol,TF3,SERIES_LASTBAR_DATE);    //Calé sur TF3
   bool NewBarFlag               =  (dtBarCurrent!=dtBarPrevious); 
   
   
/*---------------------------------Indicateur----------------------------------*/

//Ichimoku---------------------------------------------------------

   ichimokuTF1.Refresh(-1);
   double TenkanSenValueTF1      =  ichimokuTF1.TenkanSen(0);
   double KijunSenValueTF1       =  ichimokuTF1.KijunSen(0);
   double SenKouSpanAValueTF1    =  ichimokuTF1.SenkouSpanA(-26);
   double SenKouSpanBValueTF1    =  ichimokuTF1.SenkouSpanB(-26);
   double SKSpanANowValueTF1     =  ichimokuTF1.SenkouSpanA(0);
   double SKSpanBNowValueTF1     =  ichimokuTF1.SenkouSpanB(0);
   double ChinkouSpanAValueTF1   =  ichimokuTF1.ChinkouSpan(26);
   
   ichimokuTF2.Refresh(-1);
   double TenkanSenValueTF2      =  ichimokuTF2.TenkanSen(0);
   double KijunSenValueTF2       =  ichimokuTF2.KijunSen(0);
   double SenKouSpanAValueTF2    =  ichimokuTF2.SenkouSpanA(-26);
   double SenKouSpanBValueTF2    =  ichimokuTF2.SenkouSpanB(-26);
   double SKSpanANowValueTF2     =  ichimokuTF2.SenkouSpanA(0);
   double SKSpanBNowValueTF2     =  ichimokuTF2.SenkouSpanB(0);   
   double ChinkouSpanAValueTF2   =  ichimokuTF2.ChinkouSpan(26);
   
   ichimokuTF3.Refresh(-1);
   double TenkanSenValueTF3      =  ichimokuTF3.TenkanSen(0);
   double KijunSenValueTF3       =  ichimokuTF3.KijunSen(0);
   double SenKouSpanAValueTF3    =  ichimokuTF3.SenkouSpanA(-26);
   double SenKouSpanBValueTF3    =  ichimokuTF3.SenkouSpanB(-26);
   double SKSpanANowValueTF3     =  ichimokuTF3.SenkouSpanA(0);
   double SKSpanBNowValueTF3     =  ichimokuTF3.SenkouSpanB(0);   
   double ChinkouSpanAValueTF3   =  ichimokuTF3.ChinkouSpan(26);
   
/*---------------------------------Objets----------------------------------*/

   if (NewBarFlag==true)
      { 
         ObjectMove(_Symbol,"A_TF1",0,0,SKSpanANowValueTF1);
         ObjectMove(_Symbol,"B_TF1",0,0,SKSpanBNowValueTF1);
         ObjectMove(_Symbol,"A_TF2",0,0,SKSpanANowValueTF2);
         ObjectMove(_Symbol,"B_TF2",0,0,SKSpanBNowValueTF2);
      }

/*-------------------------Valeur Haute la plus proche--------------------*/



/*-------------------------Valeur Basse la plus proche--------------------*/
  
 
/*Ouverture de positions*/

   if (PositionsTotal()==0)
      {
      
      }/*Fin d'ouverture de position*/ 
 
}/*Fin OnTick*/


void A_TF1Line()
{
   ObjectCreate(_Symbol,"A_TF1",OBJ_HLINE,0,0,SKSpanANowValueTF1);
   ObjectSetInteger(0,"A_TF1",OBJPROP_COLOR,clrMaroon);
   ObjectSetInteger(0,"A_TF1",OBJPROP_WIDTH,1);                 
}

void B_TF1Line()
{
   ObjectCreate(_Symbol,"B_TF1",OBJ_HLINE,0,0,SKSpanBNowValueTF1);
   ObjectSetInteger(0,"B_TF1",OBJPROP_COLOR,clrBrown);
   ObjectSetInteger(0,"B_TF1",OBJPROP_WIDTH,1);                 
}

void A_TF2Line()
{
   ObjectCreate(_Symbol,"A_TF2",OBJ_HLINE,0,0,SKSpanANowValueTF2);
   ObjectSetInteger(0,"A_TF2",OBJPROP_COLOR,clrSteelBlue);
   ObjectSetInteger(0,"A_TF2",OBJPROP_WIDTH,1);                 
}

void B_TF2Line()
{
   ObjectCreate(_Symbol,"B_TF2",OBJ_HLINE,0,0,SKSpanBNowValueTF2);
   ObjectSetInteger(0,"B_TF2",OBJPROP_COLOR,clrLightBlue);
   ObjectSetInteger(0,"B_TF2",OBJPROP_WIDTH,1);                 
}




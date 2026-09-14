//+------------------------------------------------------------------+
//|                                  LiteFinance_Quant_Bridge.mq5     |
//|                        AI Quant Autonomous Trading Bridge         |
//+------------------------------------------------------------------+
#property copyright "AI Studio Quant Trading System"
#property link      "https://ai.studio/build"
#property version   "2.00"
#property strict

input string WebhookURL = "https://ais-dev-mcyrxojl6ieifg2g7jwrq4-642489029202.europe-west2.run.app/api/v1/mt5/sync";
input int SyncIntervalSeconds = 3;

int timerCounter = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("🚀 LiteFinance AI Quant Bridge Initialized for Account: ", AccountInfoInteger(ACCOUNT_LOGIN));
   EventSetTimer(SyncIntervalSeconds);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("🛑 LiteFinance AI Quant Bridge Stopped.");
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
   SyncWithQuantServer();
}

//+------------------------------------------------------------------+
//| Sync Account Info with Cloud Quant Server                        |
//+------------------------------------------------------------------+
void SyncWithQuantServer()
{
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   string server = AccountInfoString(ACCOUNT_SERVER);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   int total_positions = PositionsTotal();

   string jsonPayload = StringFormat(
      "{\"account_number\":\"%I64d\",\"server_name\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,\"leverage\":\"1:%d\",\"positions_count\":%d}",
      login, server, balance, equity, margin, free_margin, (int)leverage, total_positions
   );

   char postData[];
   char resultData[];
   string resultHeaders;
   StringToCharArray(jsonPayload, postData, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postData, ArraySize(postData) - 1); // remove null terminator

   string headers = "Content-Type: application/json\r\n";
   int res = WebRequest("POST", WebhookURL, headers, 3000, postData, resultData, resultHeaders);

   if (res == 200)
   {
      // Synced successfully
   }
   else if (res == -1)
   {
      // Note: Enable WebRequest in MT5: Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL
   }
}

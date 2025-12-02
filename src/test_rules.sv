module adc_controller (
    input wire clock_125m,      // Нарушение правила 9: должен быть CLK или CLK125M
    input wire reset,          // Нарушение правила 10: должен быть RST_N
    input wire [7:0] data_in,
    output reg [7:0] data_out,
    output reg valid_f
);

// Нарушение правила 1: не уникальное название блока
module adc_controller;  // Дублирует название верхнего модуля

    // Нарушение правила 4: внутренний сигнал с заглавными буквами
    reg [7:0] Buffer;

    // Нарушение правила 5: флаг без суффикса _f
    reg overflow_flag;
    
    // Правильный флаг (соответствует правилу 5)
    reg underflow_f;

    // Нарушение правила 9: второй тактовый сигнал с неправильным именем
    input wire clk_adc;  // Должен быть CLK или с указанием частоты

    // Нарушение правила 10: второй сброс с неправильным именем  
    input wire reset_adc;  // Должен быть RST_N или RST_XXX_N

    // Правильные названия (для примера)
    parameter CLK_FREQ = 125_000_000;
    
    // Состояния автомата (правило 2 соблюдено)
    typedef enum logic [2:0] {
        IDLE_ST,
        CONFIG_ST,
        SAMPLE_ST,
        CONVERT_ST,
        OUTPUT_ST
    } state_t;
    
    state_t CURRENT_STATE, NEXT_STATE;

    // Счётчик (правило 20 соблюдено)
    reg [15:0] cnt_samples;
    
    // Таймер (правило 21 соблюдено)
    reg timeout_tmr;

    // Мост (нарушение правила 6: неправильная конструкция названия)
    module spi2ahb_bridge;  // Должно быть spi2ahb_br
    
    // Мост с правильным названием (для примера)
    module axi2ahb_br;  // Правильно

    // Нарушение правила 1: опять не уникальное название
    module data_processor;
    
    // Ещё один блок с не уникальным названием
    module data_processor;  // Дублирует предыдущее

    always @(posedge clock_125m or negedge reset) begin
        if (!reset) begin
            CURRENT_STATE <= IDLE_ST;
            cnt_samples <= 16'h0;
            data_out <= 8'h00;
            valid_f <= 1'b0;
        end else begin
            CURRENT_STATE <= NEXT_STATE;
            
            case (CURRENT_STATE)
                IDLE_ST: begin
                    if (data_in[0]) begin
                        NEXT_STATE <= CONFIG_ST;
                    end
                end
                CONFIG_ST: begin
                    NEXT_STATE <= SAMPLE_ST;
                    cnt_samples <= cnt_samples + 1;
                end
                SAMPLE_ST: begin
                    NEXT_STATE <= CONVERT_ST;
                    Buffer <= data_in;  // Использование сигнала с нарушением правила 4
                end
                CONVERT_ST: begin
                    NEXT_STATE <= OUTPUT_ST;
                    data_out <= Buffer ^ 8'h55;
                end
                OUTPUT_ST: begin
                    NEXT_STATE <= IDLE_ST;
                    valid_f <= 1'b1;
                    // Нарушение правила 5
                    overflow_flag = (cnt_samples == 16'hFFFF);
                end
            endcase
        end
    end

    // Пример интерфейса (правило 10 таблицы)
    interface spi_if_t;
        logic sclk;
        logic mosi;
        logic miso;
        logic cs_n;
        
        modport mst (
            output sclk, mosi, cs_n,
            input miso
        );
        
        modport slv (
            input sclk, mosi, cs_n,
            output miso
        );
    endinterface

    // Экземпляр интерфейса (правило 13)
    spi_if_t spi_if();

endmodule

// Ещё один модуль с нарушениями
module data_processor (  // Нарушение правила 1: неуникальное название (уже было выше)
    input clk,           // Нарушение правила 9: должен быть CLK
    input rst,           // Нарушение правила 10: должен быть RST_N
    input [15:0] data_in
);
    
    // Нарушение правила 8: заглавные буквы в названии сигнала
    reg [15:0] TEMP_REG;
    
    // Пересинхронизатор (правило 18)
    reg [2:0] sync_3st;

    always @(posedge clk) begin
        TEMP_REG <= data_in;
        sync_3st <= {sync_3st[1:0], data_in[0]};
    end

endmodule
module phy_rmii_to_mii_tx
#(
    parameter TIME_TRANS_RMII_TWO = 20,
    TIME_TRANS_RMII_ONE = 10,
    DSIZE = 6,
    ASIZE = 4,
    MEMDEPTH = 1<<ASIZE,
    TRESHOLD_ALLMOST_EMPTY = 1,
    TRESHOLD_ALLMOST_FULL = 1
)

(
    input logic RST_N_MAC, RST_N_PHY,
    input logic TX_CLK,
    // Шина RMII интерфейса
    rmii_tx_if_t IN_IFP,
    // Шина MII интерфейса
    mii_tx_if_t OUT_IFP
);



logic [7:0] cnt_bit;
logic [3:0] data_reg;
logic wr_inc;
logic rd_inc;
logic [5:0] wr_data, rd_data;
logic empty, almost_empty;

//запись данных
// согласно протоколу данные с MAC - уровня держатся 10 тактов
// сохранять данные следует на 10 - ом такте
always_ff @(posedge IN_IFP.CLK_IN or negedge RST_N_MAC) 
if (!RST_N_MAC) begin
    cnt_bit <= '0;
    wr_inc <= '0;
end
else begin
    if (IN_IFP.TX_EN) begin
        cnt_bit <= cnt_bit + 'b1;
        if (cnt_bit == TIME_TRANS_RMII_ONE) begin
            data_reg [3:2] <= IN_IFP.TXD;
            wr_inc <= '1;
        end
        else if (cnt_bit < TIME_TRANS_RMII_ONE)
            data_reg [1:0] <= IN_IFP.TXD;
        else wr_inc <= '0;
    
        if (cnt_bit >= TIME_TRANS_RMII_TWO)
        cnt_bit <= '0;
    end
    else cnt_bit <= '0;
end

assign wr_data[5] = '0;
assign wr_data [4] = IN_IFP.TX_EN;
assign wr_data [3:0] = data_reg [3:0];

fifo_a #(DSIZE, ASIZE, MEMDEPTH,TRESHOLD_ALLMOST_EMPTY,
TRESHOLD_ALLMOST_FULL) u_fifo_tx_a
(
    .RST_RX_N (RST_N_PHY),
    .RST_TX_N (RST_N_MAC),
    .WR_CLK (IN_IFP.CLK_IN),
    .RD_CLK (TX_CLK),
    .WR_EN (wr_inc),
    .WR_DATA (wr_data),
    .RD_EN (rd_inc),
    .RD_DATA (rd_data),
    .EMPTY (empty),
    .ALMOST_EMPTY (almost_empty)
);

// logic [1:0] emp_al_emp;
// assign emp_al_emp = {empty, almost_empty};

// enum logic [1:0] {
//     en_rec_1 = 2'b00,
//     en_rec_2 = 2'b01,
//     dis_rec = 2'b11
// } status_control;

always_comb begin
    case (RST_N_PHY)
        '0: begin
            OUT_IFP.TX_ER = '0;
            OUT_IFP.TX_EN = '0;
            OUT_IFP.TXD = 'x;
            rd_inc = '0;
        end
        '1: begin
           case (empty)
            '1: begin
                rd_inc = '0;
                OUT_IFP.TX_EN = '0;
                OUT_IFP.TXD = '0;
                OUT_IFP.TX_ER = '0;
            end
            '0: begin
                rd_inc = '1;
                OUT_IFP.TX_ER = '0;
                OUT_IFP.TX_EN = rd_data [4];
                OUT_IFP.TXD = rd_data [3:0];
            end
           endcase 
        end
        default: begin
        OUT_IFP.TX_ER = 'x;
        rd_inc = 'x;
        end 
    endcase
end

endmodule
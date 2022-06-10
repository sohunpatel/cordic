module lut (
    input [3:0] i,
    input [1:0] mode,
    output signed [31:0] e
);

localparam CIRCULAR = 2'b00;
localparam LINEAR = 2'b01;
localparam HYPERBOLIC = 2'b10;

reg signed [31:0] out;

always @(*) begin
    if (mode == CIRCULAR) begin
        case (i)
            4'd00: out = 32'hc910;
            4'd01: out = 32'h76b2;
            4'd02: out = 32'h3eb7;
            4'd03: out = 32'h1fd6;
            4'd04: out = 32'h0ffb;
            4'd05: out = 32'h07ff;
            4'd06: out = 32'h0400;
            4'd07: out = 32'h0200;
            4'd08: out = 32'h0100;
            4'd09: out = 32'h0080;
            4'd10: out = 32'h0040;
            4'd11: out = 32'h0020;
            4'd12: out = 32'h0010;
            4'd13: out = 32'h0008;
            4'd14: out = 32'h0004;
            4'd15: out = 32'h0002;
            default: out = 32'h0;
        endcase
    end else if (mode == LINEAR) begin
        out = 1 <<< (16 - i);
    end else if (mode == HYPERBOLIC) begin
        case (i)
            4'd00: out = 32'h8c9f;
            4'd01: out = 32'h4163;
            4'd02: out = 32'h202b;
            4'd03: out = 32'h1005;
            4'd04: out = 32'h0801;
            4'd05: out = 32'h0400;
            4'd06: out = 32'h0200;
            4'd07: out = 32'h0100;
            4'd08: out = 32'h0080;
            4'd09: out = 32'h0040;
            4'd10: out = 32'h0020;
            4'd11: out = 32'h0010;
            4'd12: out = 32'h0008;
            4'd13: out = 32'h0004;
            4'd14: out = 32'h0002;
            4'd15: out = 32'h0001;
            default: out = 0;
        endcase
    end else begin
        out = 32'h0000;
     end
end

assign e = out;

endmodule

module top (
    // Clock and reset
    input clk_i,
    input rstn_i,
    // Data valid signals
    input valid_i,
    output valid_o,
    // CORDIC modes
    input [1:0] mode,
    input rotational,
    // Inputs
    input signed [31:0] x_i,
    input signed [31:0] y_i,
    input signed [31:0] z_i,
    // Outputs
    output signed [31:0] x_o,
    output signed [31:0] y_o,
    output signed [31:0] z_o
);

localparam CIRCULAR = 2'b00;
localparam LINEAR = 2'b01;
localparam HYPERBOLIC = 2'b10;

reg signed [31:0] x;
reg signed [31:0] y;
reg signed [31:0] z;

reg signed [31:0] diffx;
reg signed [31:0] diffy;

reg signed [31:0] e;
reg [3:0] i;
reg d;

reg [1:0] state;
reg valid;

localparam IDLE = 2'b00;
localparam READ = 2'b01;
localparam CALC = 2'b10;
localparam WRITE = 2'b11;

assign d = rotational ? (z > 0) : (x_i[31] & y_i[31] == 1);

lut LUT (
    .i (i),
    .mode (mode),
    .e (e)
);

// FSM
always @(posedge clk_i) begin
    if (!rstn_i) begin
        x <= 0;
        y <= 0;
        z <= 0;
        i <= 0;
        valid <= 0;
        state <= IDLE;
    end else if (state == IDLE && valid_i == 1'b1) begin
        state <= READ;
    end else if (state == READ) begin
        state <= CALC;
    end else if (state == CALC && i == 4'b1111) begin
        state <= WRITE;
    end else if (state == WRITE) begin
        state <= IDLE;
    end
end

always @(posedge clk_i) begin
    case (state)
    IDLE: begin
        valid <= 1'b0; 
    end
    READ: begin
        x <= x_i;
        y <= y_i;
        z <= z_i;
        valid <= 0;
    end
    CALC: begin
        if (mode == CIRCULAR) begin
            x <= (d) ? (x - (y >>> i)) : (x + (y >>> i));
        end else if (mode == LINEAR) begin
            x <= x_i;
        end else if (mode == HYPERBOLIC) begin
            x <= (d) ? (x + (y >>> i)) : (x - (y >>> i));
        end
        y <= (d) ? (y + (x >>> i)) : (y - (x >>> i));
        z <= (d) ? (z - e) : (z + e);
        i <= i + 1;
    end
    WRITE: begin
        valid <= 1'b1;
    end
    default: ;
    endcase
end

assign valid_o = valid;
assign x_o = x;
assign y_o = y;
assign z_o = z;

`ifndef VERILATOR
initial begin
    integer idx;
    $dumpfile("dump.vcd");
    $dumpvars(1, top);
end
`endif

endmodule

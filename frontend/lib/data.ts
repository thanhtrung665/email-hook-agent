// lib/data.ts
export const LABELS = [
    { id: "INQUIRY", name: "Inquiry (Hỏi đáp)" },
    { id: "QUOTE", name: "Quote (Yêu cầu báo giá)" },
    { id: "PO", name: "PO (Đơn đặt hàng)" },
    { id: "PROFORMA_INVOICE", name: "Proforma Invoice" },
    { id: "MISA_MVPO", name: "Misa MVPO" },
    { id: "SOA", name: "Sales Order Acknowledgement" },
    { id: "CIPL_CERTIFICATES", name: "CIPL / Certificates" },
    { id: "ORDER_PICTURE", name: "Order Picture" },
    { id: "AWB_BOL", name: "AWB/BOL" },
    { id: "SED", name: "SED (Tờ khai Mỹ)" },
    { id: "SHIPMENT_DOCUMENT", name: "Shipment Document" },
    { id: "DELIVERY_TICKET", name: "Delivery Ticket" },
    { id: "EXCEPTION", name: "Exception (Ngoại lệ)" },
    { id: "SPAM_ADS", name: "Quảng cáo (Bỏ qua)" },
];

export const MOCK_EMAILS = [
    {
        id: "1",
        sender: { name: "Nguyễn Văn An", email: "an.nguyen@baobiminhphat.vn", avatar: "VA", company: "Công ty TNHH Bao Bì" },
        subject: "Hóa đơn tháng 9 - PO-2026-118",
        time: "08:05 23/9/26",
        tldr: "Minh Phát gửi hóa đơn GTGT số 0001234 cho đơn hàng PO-2026-118, tổng giá trị 45.600.000 đ đã gồm VAT.",
        tags: ["Hóa đơn / Thanh toán", "Đơn hàng"],
        files: 1,
        actionItems: 2,
        isUrgent: true,
    },
    {
        id: "2",
        sender: { name: "Phạm Minh Đức", email: "duc.pham@haiduong.vn", avatar: "MĐ", company: "Nhà Phân Phối HD" },
        subject: "Đề nghị báo giá phần mềm quản lý kho",
        time: "11:00 23/9/26",
        tldr: "Bên em là nhà phân phối tại Hải Dương, đang cần báo giá phần mềm quản lý kho cho 3 kho.",
        tags: ["Cơ hội bán hàng"],
        files: 0,
        actionItems: 2,
        isUrgent: false,
    },
    {
        id: "3",
        sender: { name: "Giám đốc CongtyABC", email: "giamdoc@congtyabc.vn", avatar: "ĐC", company: "Đối tác" },
        subject: "Chuyển khoản gấp cho đối tác",
        time: "10:30 23/9/26",
        tldr: "Anh đang họp không nghe máy được. Yêu cầu chuyển tiền gấp vào tài khoản cá nhân.",
        tags: ["Khẩn cấp"],
        files: 0,
        actionItems: 1,
        isUrgent: true,
        securityFlag: "Nghi ngờ lừa đảo - không làm theo yêu cầu chuyển tiền/đổi tài khoản"
    }
];
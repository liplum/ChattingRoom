using System.ComponentModel;
using System.ComponentModel.DataAnnotations;

namespace ChattingRoom.Core.DB.Models;
#nullable disable
public enum JoinRoomRequestResult {
    None = 0, Accept = 1, Refuse = 2, Dismiss = 3,
}

public class JoinRoomRequest {
    [Key]
    public int JoinRoomRequestId { get; set; }
    [Required]
    public User Applicant { get; set; }
    [Required]
    public ChatRoom ChatRoom { get; set; }
    [Required]
    public DateTime CreatedTime { get; set; }
    [Required, DefaultValue(JoinRoomRequestResult.None)]
    public JoinRoomRequestResult Result { get; set; }
}